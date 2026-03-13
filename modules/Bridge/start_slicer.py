"""
start_slicer.py — Launch Slicer GUI and exit once the socket is ready.

The Slicer window stays open as an independent process.
Use inject.py to send actions to the running Slicer.

Run:
  python3 start_slicer.py
"""
import os, socket, subprocess, sys, time
from pathlib import Path

ROOT           = Path(__file__).parent.parent.parent
SLICER_BIN     = str(ROOT / "Slicer-5.10.0-linux-amd64/Slicer")
BOOTSTRAP      = str(Path(__file__).parent / "slicer_use/slicer/bootstrap.py")
SOCK_PATH      = "/tmp/slicer_agent.sock"
PUSH_SOCK_PATH = "/tmp/slicer_agent_push.sock"
PUSH_LOG_PATH  = "/tmp/slicer_push.jsonl"
TIMEOUT        = 120.0

if os.path.exists(SOCK_PATH):
    os.remove(SOCK_PATH)

print("Starting Slicer (GUI mode)…")
subprocess.Popen(
    [SLICER_BIN, "--python-script", BOOTSTRAP, "--no-splash"],
    env={
        **os.environ,
        "SLICER_SOCK": SOCK_PATH,
        "SLICER_PUSH_SOCK": PUSH_SOCK_PATH,
        "SLICER_PUSH_LOG": PUSH_LOG_PATH,
        "SLICER_BOOTSTRAP_LOG": "/tmp/slicer_bootstrap.log",
    },
)

# Wait for socket to appear
deadline = time.monotonic() + TIMEOUT
while time.monotonic() < deadline:
    if os.path.exists(SOCK_PATH):
        # Also verify it's listening
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCK_PATH)
            s.close()
            print(f"Slicer ready — socket at {SOCK_PATH}")
            print("Use inject.py to send actions.")
            sys.exit(0)
        except ConnectionRefusedError:
            pass
    time.sleep(0.2)

print("ERROR: Slicer did not start in time. Check /tmp/slicer_bootstrap.log")
sys.exit(1)
