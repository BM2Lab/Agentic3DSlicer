"""
bootstrap.py — injected into Slicer at startup via --python-script.

Starts two Unix domain socket servers in daemon threads:
  1. Request socket  (SLICER_SOCK, default /tmp/slicer_agent.sock)
     — request/response RPC: agent sends code, Slicer returns result
  2. Push socket     (SLICER_PUSH_SOCK, default /tmp/slicer_agent_push.sock)
     — async push: Slicer sends events to all connected listeners unprompted

ALL exec() calls are dispatched to the Qt main thread via a thread-safe work queue.
The main thread's timer drains the queue, so Qt/MRML objects are always created safely.

Request Protocol:
  Request:  {"id": "<uuid>", "code": "<python>"}\n
  Response: {"id": "<uuid>", "result": <any>, "stdout": "<str>", "error": "<str|null>"}\n

Push Protocol (newline-delimited JSON, Slicer → agent):
  {"type": "vtk_warning",   "text": "...", "ts": 1234567890.123}
  {"type": "vtk_error",     "text": "...", "ts": ...}
  {"type": "vtk_text",      "text": "...", "ts": ...}
  {"type": "python_error",  "text": "...", "ts": ...}
  {"type": "stdout",        "text": "...", "ts": ...}
  {"type": "mrml_event",    "event": "NodeAdded", "node_id": "...", "node_class": "...", "node_name": "...", "ts": ...}

VTK capture during exec:
  vtkStringOutputWindow is swapped in during capturing_exec() so that C++-triggered
  VTK warnings are intercepted. After exec, captured output is:
    - included in the RPC response stdout field
    - forwarded through the original output window (preserves Python interactor colors)
    - pushed to all push listeners as typed events

Note on permanent VTK hook:
  VTK C++ virtual dispatch does NOT call Python method overrides on vtkOutputWindow
  subclasses. A permanent hook for Python-interactor-triggered VTK warnings requires
  slicer.app.errorLogModel() observers (planned for Phase 4).

State:
  _globs persists across requests. 'slicer' and 'qt' are pre-seeded.
  Assign __result__ inside exec'd code to return a value.
"""
import socket, threading, queue, json, traceback, io, os, sys, time
import slicer, qt, vtk

SOCK_PATH      = os.environ.get("SLICER_SOCK",      "/tmp/slicer_agent.sock")
PUSH_SOCK_PATH = os.environ.get("SLICER_PUSH_SOCK", "/tmp/slicer_agent_push.sock")
_LOG_PATH      = os.environ.get("SLICER_BOOTSTRAP_LOG", "")
PUSH_LOG_PATH  = os.environ.get("SLICER_PUSH_LOG",  "/tmp/slicer_push.jsonl")

# Persistent namespace — survives across all requests
_globs: dict = {"slicer": slicer, "qt": qt}

# Work queue: handler threads post items; main thread drains via timer
_exec_queue: queue.Queue = queue.Queue()

# Push clients
_push_clients: list = []
_push_lock = threading.Lock()


def _log(msg: str):
    """Thread-safe file logging (never calls print from background threads)."""
    if _LOG_PATH:
        with open(_LOG_PATH, "a") as f:
            f.write(msg + "\n")


# ── Push socket ──────────────────────────────────────────────────────────────

def push(event: dict):
    """Send a push event to all connected listeners and append to log file. Thread-safe."""
    event.setdefault("ts", time.time())
    line = json.dumps(event)
    data = line.encode() + b"\n"
    with _push_lock:
        dead = []
        for client in _push_clients:
            try:
                client.sendall(data)
            except OSError:
                dead.append(client)
        for d in dead:
            _push_clients.remove(d)

    # Append to persistent jsonl log for post-hoc inspection.
    # Best-effort only — logging failures must not break Slicer.
    try:
        if PUSH_LOG_PATH:
            with open(PUSH_LOG_PATH, "a") as f:
                f.write(line + "\n")
    except OSError:
        pass


def serve_push():
    try:
        if os.path.exists(PUSH_SOCK_PATH):
            os.remove(PUSH_SOCK_PATH)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(PUSH_SOCK_PATH)
        srv.listen(5)
        _log(f"[push] socket bound at {PUSH_SOCK_PATH}")
        while True:
            try:
                conn, _ = srv.accept()
                with _push_lock:
                    _push_clients.append(conn)
                _log("[push] client connected")
            except OSError as e:
                _log(f"[push] accept error: {e}")
    except Exception as e:
        _log(f"[push] serve_push() FATAL: {e}\n{traceback.format_exc()}")


# ── Exec ─────────────────────────────────────────────────────────────────────

def capturing_exec(code: str) -> tuple:
    """
    Run code in _globs. Capture sys.stdout/sys.stderr AND VTK warnings.
    Call ONLY from the Qt main thread.
    Returns (result, stdout_str, error_str_or_None).

    VTK output is captured via vtkStringOutputWindow swap (works for C++-triggered
    warnings), then forwarded to the original window (preserves interactor colors)
    and pushed to all push listeners.
    """
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf = io.StringIO()

    # Swap in capture window — works for C++-triggered VTK output
    vtk_win = vtk.vtkStringOutputWindow()
    old_vtk_win = vtk.vtkOutputWindow.GetInstance()
    vtk.vtkOutputWindow.SetInstance(vtk_win)

    result = None
    error = None
    try:
        exec(code, _globs)
        result = _globs.pop("__result__", None)
    except Exception:
        error = traceback.format_exc()
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        vtk.vtkOutputWindow.SetInstance(old_vtk_win)

    stdout = buf.getvalue()
    vtk_out = vtk_win.GetOutput()

    if vtk_out and vtk_out.strip():
        # Forward to original window to preserve Python interactor colors
        # and push each chunk as a typed event
        for chunk in vtk_out.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "Warning:" in chunk:
                push({"type": "vtk_warning", "text": chunk})
                old_vtk_win.DisplayWarningText(chunk + "\n")
            elif "Error:" in chunk:
                push({"type": "vtk_error", "text": chunk})
                old_vtk_win.DisplayErrorText(chunk + "\n")
            else:
                push({"type": "vtk_text", "text": chunk})
                old_vtk_win.DisplayText(chunk + "\n")
        prefix = "\n" if stdout else ""
        stdout += prefix + vtk_out

    # Push stdout and Python errors
    if stdout and stdout.strip():
        push({"type": "stdout", "text": stdout.strip()})
    if error:
        push({"type": "python_error", "text": error})

    return result, stdout, error


# ── Request socket ────────────────────────────────────────────────────────────

def _drain_exec_queue():
    """
    Called by the keepalive QTimer on the Qt main thread (every 10ms).
    Drains all pending exec requests, runs them, and wakes waiting handler threads.
    """
    while not _exec_queue.empty():
        try:
            code, done_event, result_box = _exec_queue.get_nowait()
        except queue.Empty:
            break
        r, o, e = capturing_exec(code)
        result_box[:] = [r, o, e]
        done_event.set()


def main_thread_exec(code: str, timeout: float = 60.0) -> tuple:
    """
    Submit code for execution on the Qt main thread and block until done.
    Safe to call from any background thread.
    """
    done_event = threading.Event()
    result_box = [None, "", None]
    _exec_queue.put((code, done_event, result_box))
    done_event.wait(timeout=timeout)
    return tuple(result_box)


def handle(conn: socket.socket):
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    req = json.loads(line)
                except json.JSONDecodeError as e:
                    resp = {"id": "?", "result": None, "stdout": "", "error": f"JSON decode error: {e}"}
                    conn.sendall(json.dumps(resp).encode() + b"\n")
                    continue

                result, stdout, error = main_thread_exec(req["code"])
                resp = {
                    "id":     req["id"],
                    "result": result,
                    "stdout": stdout,
                    "error":  error,
                }
                try:
                    conn.sendall(json.dumps(resp).encode() + b"\n")
                except OSError:
                    break
    except OSError:
        pass
    finally:
        conn.close()


def serve():
    try:
        if os.path.exists(SOCK_PATH):
            os.remove(SOCK_PATH)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(SOCK_PATH)
        srv.listen(5)
        _log(f"[bootstrap] socket bound at {SOCK_PATH}")
        while True:
            try:
                conn, _ = srv.accept()
                _log("[bootstrap] client connected")
                threading.Thread(target=handle, args=(conn,), daemon=True).start()
            except OSError as e:
                _log(f"[bootstrap] accept error: {e}")
    except Exception as e:
        _log(f"[bootstrap] serve() FATAL: {e}\n{traceback.format_exc()}")


# ── Error log observer (Phase 4) ─────────────────────────────────────────────

_LOG_LEVEL_TYPE = {
    "Warning":  "log_warning",
    "Error":    "log_error",
    "Critical": "log_error",
    "Fatal":    "log_error",
    "Info":     "log_info",
    "Debug":    "log_debug",
}


def _install_error_log_observer():
    """
    Install observer on slicer.app.errorLogModel() to push ALL Slicer messages
    including those from the Python interactor — achieving true bidirectional messaging.

    Deferred via QTimer.singleShot(0) to run after the event loop starts,
    when errorLogModel is fully initialised.
    """
    try:
        model = slicer.app.errorLogModel()
        _baseline = [model.rowCount()]  # only push rows added after observer install

        def _on_rows_inserted(parent, first, last):
            # Skip rows that existed before observer install
            if last < _baseline[0]:
                return
            start = max(first, _baseline[0])
            for row in range(start, last + 1):
                # Columns: 0=Time, 1=icon, 2=Level, 3=Origin/Category, 4=Description
                level    = str(model.data(model.index(row, 2)) or "").strip()
                category = str(model.data(model.index(row, 3)) or "").strip()
                text     = str(model.data(model.index(row, 4)) or "").strip()
                if not text:
                    continue
                event_type = _LOG_LEVEL_TYPE.get(level, "log_info")
                push({"type": event_type, "level": level, "category": category, "text": text})

        model.connect("rowsInserted(QModelIndex,int,int)", _on_rows_inserted)
        _log("[push] errorLogModel observer installed")
        print("[bootstrap] errorLogModel observer installed", flush=True)
    except Exception as e:
        _log(f"[push] errorLogModel observer FAILED: {e}\n{traceback.format_exc()}")


# ── Startup ───────────────────────────────────────────────────────────────────

threading.Thread(target=serve,      daemon=True).start()
threading.Thread(target=serve_push, daemon=True).start()

# Keepalive timer: fires on Qt main thread every 10ms.
# Dual purpose: (1) keeps the event loop alive, (2) drains the exec work queue.
_keepalive = qt.QTimer()
_keepalive.setInterval(10)
_keepalive.timeout.connect(_drain_exec_queue)
_keepalive.start()

# Defer observer install so the event loop and errorLogModel are fully ready
qt.QTimer.singleShot(500, _install_error_log_observer)

print(f"[bootstrap] socket ready at {SOCK_PATH}", flush=True)
print(f"[bootstrap] push   socket at {PUSH_SOCK_PATH}", flush=True)
