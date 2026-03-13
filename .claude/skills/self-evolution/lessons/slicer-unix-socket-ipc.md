# Slicer Unix Socket IPC — Lessons

**Verified:** 2026-03-12 (Slicer 5.10.0, Linux)
**Task:** Build a Unix domain socket bridge so an external process can exec Python inside a running Slicer instance and read results.

---

## 1. Slicer exits after --python-script returns in --no-main-window mode

**Problem:** Launching Slicer headless with `--no-main-window --python-script bootstrap.py` — the bootstrap starts a daemon thread and returns. Slicer then exits, killing all threads before any connection arrives.

**Fix:** Start a Qt keepalive timer in the bootstrap (on the main thread):
```python
import qt
_keepalive = qt.QTimer()
_keepalive.setInterval(1000)
_keepalive.timeout.connect(lambda: None)
_keepalive.start()
```
This holds the Qt event loop open indefinitely. Slicer stays alive and the daemon threads keep running.

---

## 2. bind() creates the socket file before listen() — race condition ECONNREFUSED

**Problem:** `os.path.exists(sock_path)` returns `True` as soon as `socket.bind()` is called. But `listen()` is called immediately after. If the client connects between `bind()` and `listen()`, it gets `ConnectionRefusedError`.

**Fix:** Client must retry connect on ECONNREFUSED instead of failing immediately:
```python
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
for _ in range(50):
    try:
        sock.connect(SOCK_PATH)
        break
    except ConnectionRefusedError:
        time.sleep(0.1)
else:
    raise RuntimeError("no listener after retries")
```

---

## 3. print() from background threads is not thread-safe in PythonQt

**Problem:** Slicer installs C-level hooks as `sys.stdout` and `sys.stderr`. Calling `print()` from a daemon/socket thread can cause crashes or garbled output because PythonQt's stream hook is not designed for concurrent writes.

**Fix:** Use file-based logging from all background threads:
```python
_LOG_PATH = os.environ.get("SLICER_BOOTSTRAP_LOG", "")

def _log(msg: str):
    if _LOG_PATH:
        with open(_LOG_PATH, "a") as f:
            f.write(msg + "\n")
```
Only call `print()` from the main thread (e.g., the last line of the bootstrap script, before the event loop starts).

---

## 4. slicer.app.applicationVersion is a property, not a callable

**Problem:** `slicer.app.applicationVersion()` raises `TypeError: 'str' object is not callable`.

**Fix:** Access it as a property without `()`:
```python
version = slicer.app.applicationVersion   # correct — returns '5.10.0'
```
This is NOT listed in the docs clearly. Document it and avoid the `()` call pattern.

---

## 5. exec() in background threads is safe for read-only MRML operations

**Verified:** `slicer.mrmlScene.GetNumberOfNodes()` and similar read-only MRML queries work fine when called from socket handler threads via `exec()`. No crashes observed.

For write operations (loading volumes, creating nodes, anything that triggers Qt signals), dispatch to the main thread:
```python
qt.QTimer.singleShot(0, lambda: slicer.util.loadVolume(path))
```
The result is not immediately available — needs a callback/event pattern for async return.

---

## 6. Persistent globals across exec() calls

The bootstrap uses a module-level `_globs` dict seeded with `{"slicer": slicer, "qt": qt}`. Each `exec(code, _globs)` call mutates the same dict, so variables assigned in one call are readable in the next. The `__result__` key is popped after each call to avoid leaking values between requests.

---

## 7. Stale socket files from killed Slicer processes

`pkill -9` leaves the socket file on disk. A new Slicer starting bootstrap will call `os.remove(SOCK_PATH)` if it exists, then bind a new one. The client's `os.remove(SOCK_PATH)` at startup is also important as a safety net. Always clean up old socket files before launching a new Slicer.

---

## 8. Shell chain gotcha: pkill exit code when no process exists

`pkill -f "SlicerApp"` returns exit code 1 if no matching process is found. Using `&&` after pkill in a chain will abort the rest of the chain. Use `;` instead:
```bash
pkill -9 -f "SlicerApp" 2>/dev/null; sleep 1; rm -f /tmp/slicer_agent.sock
```

---

## 9. qt.QTimer.singleShot(0, fn) from a background thread does NOT dispatch to the main thread in PythonQt

**Problem:** Calling `qt.QTimer.singleShot(0, fn)` from a socket handler (background) thread causes:
```
QObject: Cannot create children for a parent that is in a different thread.
QObject::startTimer: Timers can only be used with threads started with QThread
```
The timer is created in the calling thread's context, not the main thread. The callback never runs on the main thread, `threading.Event.wait()` times out, and all RPC calls return `None`.

**Fix:** Use a `queue.Queue` drained by the keepalive timer that runs on the main thread:
```python
import queue, threading
_exec_queue = queue.Queue()

def _drain_exec_queue():            # called by keepalive QTimer on MAIN thread
    while not _exec_queue.empty():
        code, event, result_box = _exec_queue.get_nowait()
        r, o, e = capturing_exec(code)
        result_box[:] = [r, o, e]
        event.set()

_keepalive = qt.QTimer()
_keepalive.setInterval(10)          # 10ms polling interval
_keepalive.timeout.connect(_drain_exec_queue)
_keepalive.start()

def main_thread_exec(code, timeout=60.0):
    event = threading.Event()
    result_box = [None, "", None]
    _exec_queue.put((code, event, result_box))
    event.wait(timeout=timeout)
    return tuple(result_box)
```

---

## 10. threeDWidget(0) returns None in --no-main-window headless mode

**Problem:** `slicer.app.layoutManager().threeDWidget(0)` returns `None` in headless mode (no GUI layout is created). Calling `.threeDView()` on it raises `AttributeError: 'NoneType' object has no attribute 'threeDView'`.

**Fix:** Guard all 3D widget access and surface the error clearly:
```python
lm = slicer.app.layoutManager()
if lm is None or lm.threeDWidget(0) is None:
    raise RuntimeError("Requires GUI mode — threeDWidget is None in headless mode.")
```
Screenshot/rotation actions that depend on the 3D view require Slicer to be launched WITHOUT `--no-main-window`.
