"""
bootstrap.py — injected into Slicer at startup via --python-script.

Starts a Unix domain socket server in a daemon thread.
ALL exec() calls are dispatched to the Qt main thread via a thread-safe work queue.
The main thread's timer drains the queue, so Qt/MRML objects are always created safely.

Protocol:
  Request:  {"id": "<uuid>", "code": "<python>"}\n
  Response: {"id": "<uuid>", "result": <any>, "stdout": "<str>", "error": "<str|null>"}\n

State:
  _globs persists across requests. 'slicer' and 'qt' are pre-seeded.
  Assign __result__ inside exec'd code to return a value.

Main-thread dispatch pattern:
  Handler thread → puts (code, event, result_box) on _exec_queue
  Main thread (via keepalive QTimer at 10ms) → drains queue, runs capturing_exec, sets event
  Handler thread → event.wait() unblocks, reads result_box, sends response

  This is safe for ALL Slicer operations including volume loading and node creation.
  qt.QTimer.singleShot(0, fn) is NOT used because PythonQt does not forward it to the main
  thread when called from a background thread (it creates a timer in the calling thread
  instead, which crashes with 'Cannot create children for a parent in a different thread').
"""
import socket, threading, queue, json, traceback, io, os, sys
import slicer, qt, vtk

SOCK_PATH = os.environ.get("SLICER_SOCK", "/tmp/slicer_agent.sock")
_LOG_PATH = os.environ.get("SLICER_BOOTSTRAP_LOG", "")

# Persistent namespace — survives across all requests
_globs: dict = {"slicer": slicer, "qt": qt}

# Work queue: handler threads post items; main thread drains via timer
_exec_queue: queue.Queue = queue.Queue()


def _log(msg: str):
    """Thread-safe file logging (never calls print from background threads)."""
    if _LOG_PATH:
        with open(_LOG_PATH, "a") as f:
            f.write(msg + "\n")


def capturing_exec(code: str) -> tuple:
    """
    Run code in _globs. Capture sys.stdout/sys.stderr AND VTK warnings.
    Call ONLY from the Qt main thread.
    Returns (result, stdout_str, error_str_or_None).
    VTK warnings are appended to stdout_str prefixed with [VTK].
    """
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf = io.StringIO()

    # Redirect VTK output window to capture warnings/errors
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
        # Forward through typed VTK methods to preserve colors in Slicer's Python interactor
        for chunk in vtk_out.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "Warning:" in chunk:
                old_vtk_win.DisplayWarningText(chunk + "\n")
            elif "Error:" in chunk:
                old_vtk_win.DisplayErrorText(chunk + "\n")
            else:
                old_vtk_win.DisplayText(chunk + "\n")
        prefix = "\n" if stdout else ""
        stdout += prefix + vtk_out
    return result, stdout, error


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
    done_event  = threading.Event()
    result_box  = [None, "", None]
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


threading.Thread(target=serve, daemon=True).start()

# Keepalive timer: fires on Qt main thread every 10ms.
# Dual purpose: (1) keeps the event loop alive, (2) drains the exec work queue.
_keepalive = qt.QTimer()
_keepalive.setInterval(10)
_keepalive.timeout.connect(_drain_exec_queue)
_keepalive.start()

print(f"[bootstrap] socket ready at {SOCK_PATH}", flush=True)
