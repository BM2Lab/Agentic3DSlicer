"""
poc_test.py — Minimal proof-of-concept for the Slicer Unix socket bridge.

What it does:
  1. Launches Slicer headless with bootstrap.py injected
  2. Waits for the socket to appear
  3. Connects and runs 4 RPC tests
  4. Terminates Slicer cleanly

Run:
  cd /home/lai30/Projects/Agentic3DSlicer/modules/Bridge
  python3 poc_test.py

Lessons learned during PoC:
  - --no-main-window Slicer exits immediately after the Python script returns
    unless a qt.QTimer keepalive is running in the bootstrap.
  - bootstrapping must start the socket in a thread THEN start the QTimer
    keepalive — both are needed.
  - slicer.app.applicationVersion is a property (str), not a method.
    Do NOT call it with ().
  - Multiple Slicer instances sharing the same SLICER_SOCK path will conflict
    (second one removes the first's socket). Always kill old instances first.
  - SLICER_BOOTSTRAP_LOG env var routes thread-safe file logging from bootstrap.
"""

import json, os, socket, subprocess, sys, time, uuid
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent.parent          # Agentic3DSlicer/
SLICER    = ROOT / "Slicer-5.10.0-linux-amd64/Slicer"
BOOTSTRAP = Path(__file__).parent / "slicer_use/slicer/bootstrap.py"
SOCK_PATH = "/tmp/slicer_agent_poc.sock"
TIMEOUT_S = 60

# ── Helpers ──────────────────────────────────────────────────────────────────
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


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if os.path.exists(SOCK_PATH):
        os.remove(SOCK_PATH)

    env = {
        **os.environ,
        "SLICER_SOCK": SOCK_PATH,
        "SLICER_BOOTSTRAP_LOG": "/tmp/slicer_bootstrap.log",
        "DISPLAY": ":1",
        "XAUTHORITY": f"/run/user/{os.getuid()}/gdm/Xauthority",
    }

    print(f"[poc] Launching Slicer headless…")
    proc = subprocess.Popen(
        [str(SLICER), "--python-script", str(BOOTSTRAP),
         "--no-splash", "--no-main-window"],
        env=env,
    )

    print(f"[poc] Waiting for socket (up to {TIMEOUT_S}s)…")
    if not wait_for_socket(SOCK_PATH, TIMEOUT_S):
        proc.terminate()
        sys.exit("TIMEOUT — socket never appeared. Check /tmp/slicer_bootstrap.log")

    # Retry connect: socket file appears at bind() but listen() follows ~immediately.
    # A brief ECONNREFUSED window exists between the two — retry until connected.
    print("[poc] Socket ready. Connecting…")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    for attempt in range(50):
        try:
            sock.connect(SOCK_PATH)
            break
        except ConnectionRefusedError:
            time.sleep(0.1)
    else:
        sys.exit("Could not connect after retries")
    print("[poc] Connected.\n")

    passes = 0

    # Test 1: Slicer version (property, not callable — don't use ())
    resp = rpc(sock, "__result__ = slicer.app.applicationVersion")
    if check("slicer.app.applicationVersion", resp): passes += 1

    # Test 2: MRML scene node count
    resp = rpc(sock, "__result__ = slicer.mrmlScene.GetNumberOfNodes()")
    if check("mrmlScene.GetNumberOfNodes()", resp): passes += 1

    # Test 3: Persistent state — set a variable, read it back in a later call
    rpc(sock, "x_poc = 'persistent across calls'")
    resp = rpc(sock, "__result__ = x_poc")
    if check("persistent globals (set then read)", resp): passes += 1

    # Test 4: Capture stdout from inside Slicer
    resp = rpc(sock, "print('hello from inside slicer')")
    ok = resp["error"] is None and "hello from inside slicer" in (resp["stdout"] or "")
    print(f"  [{'PASS' if ok else 'FAIL'}] stdout capture: {resp['stdout']!r}")
    if ok: passes += 1

    print(f"\n{'='*42}")
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
