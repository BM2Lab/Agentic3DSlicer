# bootstrap.py  — injected into Slicer at startup
import socket, threading, json, traceback, slicer, os, sys, io, traceback

SOCK_PATH = os.environ.get("SLICER_SOCK", "/tmp/slicer_agent.sock")

def capturing_exec(code: str, globs: dict) -> tuple[any, str]:
    """
    Temporarily replaces PythonQt's sys.stdout/sys.stderr hooks
    with a StringIO buffer, capturing all output including VTK
    errors that PythonQt routes through the Python stream.
    """
    old_out = sys.stdout
    old_err = sys.stderr
    sys.stdout = sys.stderr = buf = io.StringIO()
    try:
        exec(code, globs)
        result = globs.get("__result__")
        error = None
    except Exception:
        result = None
        error = traceback.format_exc()
    finally:
        sys.stdout = old_out   # restore PythonQt's hook
        sys.stderr = old_err
    return result, buf.getvalue(), error

def handle(conn):
    buf = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buf += chunk
        if buf.endswith(b"\n"):          # newline-delimited JSON
            req = json.loads(buf.strip())
            buf = b""

            # Provide slicer in globals by default so simple snippets can use it
            # without an explicit import, but allow caller code to `import slicer`
            # as well. All stdout/stderr is captured via capturing_exec.
            globs = {"slicer": slicer}
            result, stdout, error = capturing_exec(req["code"], globs)

            resp = {
                "id": req["id"],
                "result": result,
                "stdout": stdout,
                "error": error,
            }
            conn.sendall(json.dumps(resp).encode() + b"\n")

def serve():
    if os.path.exists(SOCK_PATH):
        os.remove(SOCK_PATH)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK_PATH)
    srv.listen(5)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

threading.Thread(target=serve, daemon=True).start()
print(f"[slicer-agent] socket ready at {SOCK_PATH}")