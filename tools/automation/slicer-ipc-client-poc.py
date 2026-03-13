"""
Tool:        slicer-ipc-client-poc.py
Category:    automation
Tags:        IPC, unix socket, bridge, RPC, exec, remote control, client, PoC, test
Description: Minimal proof-of-concept client for the Slicer Unix socket IPC bridge.
             Launches Slicer headless with slicer-ipc-bootstrap.py, connects via Unix
             socket, runs 4 verification tests (version, scene query, persistent state,
             stdout capture), and exits cleanly.
Usage:       Set SLICER_BIN to your Slicer binary path, then: python3 slicer-ipc-client-poc.py
Version:     1.0
Verified:    2026-03-12  (Slicer 5.10.0)
"""
import json, os, socket, subprocess, sys, time, uuid
from pathlib import Path

# ── Config — edit these ───────────────────────────────────────────────────────
SLICER_BIN = "/path/to/Slicer-5.10.0-linux-amd64/Slicer"   # set to your Slicer binary
BOOTSTRAP  = Path(__file__).parent / "slicer-ipc-bootstrap.py"
SOCK_PATH  = "/tmp/slicer_agent.sock"
TIMEOUT_S  = 60   # seconds to wait for Slicer socket to appear

# ── Helpers ───────────────────────────────────────────────────────────────────
def wait_for_socket(path: str, timeout: int) -> bool:
    for _ in range(timeout * 10):
        if os.path.exists(path):
            return True
        time.sleep(0.1)
    return False


def rpc(sock: socket.socket, code: str) -> dict:
    req = json.dumps({"id": str(uuid.uuid4()), "code": code}).encode() + b"\n"
    sock.sendall(req)
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Socket closed before response")
        buf += chunk
    return json.loads(buf.split(b"\n", 1)[0])


def check(label: str, resp: dict) -> bool:
    ok = resp["error"] is None
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if resp["stdout"]:
        print(f"         stdout: {resp['stdout'].strip()}")
    if resp["error"]:
        print(f"         error:  {resp['error'].strip()[:300]}")
    else:
        print(f"         result: {resp['result']!r}")
    return ok


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if os.path.exists(SOCK_PATH):
        os.remove(SOCK_PATH)

    env = {
        **os.environ,
        "SLICER_SOCK": SOCK_PATH,
        "SLICER_BOOTSTRAP_LOG": "/tmp/slicer_bootstrap.log",
        "DISPLAY": os.environ.get("DISPLAY", ":1"),
    }

    print("[poc] Launching Slicer headless…")
    proc = subprocess.Popen(
        [SLICER_BIN, "--python-script", str(BOOTSTRAP),
         "--no-splash", "--no-main-window"],
        env=env,
    )

    print(f"[poc] Waiting for socket (up to {TIMEOUT_S}s)…")
    if not wait_for_socket(SOCK_PATH, TIMEOUT_S):
        proc.terminate()
        sys.exit("TIMEOUT — socket never appeared. Check /tmp/slicer_bootstrap.log")

    # Retry connect: socket file appears at bind() but listen() is called shortly after.
    # A brief ECONNREFUSED window exists between the two — retry until connected.
    print("[poc] Socket detected. Connecting…")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    for _ in range(50):
        try:
            sock.connect(SOCK_PATH)
            break
        except ConnectionRefusedError:
            time.sleep(0.1)
    else:
        proc.terminate()
        sys.exit("Could not connect — no listener on socket after retries")

    print("[poc] Connected.\n")
    passes = 0

    # Test 1: Slicer version (property, NOT a callable — no parentheses)
    resp = rpc(sock, "__result__ = slicer.app.applicationVersion")
    if check("slicer.app.applicationVersion (property)", resp): passes += 1

    # Test 2: Read MRML scene
    resp = rpc(sock, "__result__ = slicer.mrmlScene.GetNumberOfNodes()")
    if check("mrmlScene.GetNumberOfNodes()", resp): passes += 1

    # Test 3: Persistent state — variable set in call N is readable in call N+1
    rpc(sock, "x_ipc_test = 'persistent across calls'")
    resp = rpc(sock, "__result__ = x_ipc_test")
    if check("persistent globals (set then read)", resp): passes += 1

    # Test 4: Capture stdout from inside Slicer
    resp = rpc(sock, "print('hello from inside slicer')")
    ok = resp["error"] is None and "hello from inside slicer" in (resp["stdout"] or "")
    print(f"  [{'PASS' if ok else 'FAIL'}] stdout capture: {resp['stdout']!r}")
    if ok:
        passes += 1

    print(f"\n{'='*44}")
    print(f"Results: {passes}/4 passed")

    sock.close()
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    sys.exit(0 if passes == 4 else 1)


if __name__ == "__main__":
    main()
