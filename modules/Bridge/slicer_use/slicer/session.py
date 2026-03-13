"""
SlicerSession — manages a Slicer subprocess and its Unix socket RPC connection.

Usage:
    session = SlicerSession(slicer_bin="/path/to/Slicer")
    await session.start()
    resp = await session.run("__result__ = slicer.mrmlScene.GetNumberOfNodes()")
    print(resp["result"])   # → int
    await session.close()

Or as async context manager:
    async with SlicerSession(slicer_bin="/path/to/Slicer") as session:
        resp = await session.run("__result__ = slicer.app.applicationVersion")

RPC response dict keys:
    id      — echoed request id
    result  — value of __result__ assigned in exec'd code (None if not set)
    stdout  — captured stdout/stderr from inside Slicer
    error   — traceback string or None

Fixes applied vs reference/session.py:
    - bootstrap_path is an explicit parameter (not hardcoded to __file__.parent)
    - _sync_rpc checks for empty recv (closed socket) instead of hanging
    - connect() is retried on ECONNREFUSED (socket file appears at bind(), before listen())
    - close() calls proc.wait() with timeout after terminate()
    - DISPLAY/XAUTHORITY env vars forwarded automatically for headless X11
    - `exec` method renamed to `run` to avoid shadowing the Python builtin
"""
import asyncio, json, os, socket, subprocess, time, uuid
from pathlib import Path


# Default bootstrap path: sibling of this file
_DEFAULT_BOOTSTRAP = Path(__file__).parent / "bootstrap.py"


class SlicerSession:
    def __init__(
        self,
        slicer_bin: str,
        bootstrap_path: str | None = None,
        sock_path: str = "/tmp/slicer_agent.sock",
        push_sock_path: str = "/tmp/slicer_agent_push.sock",
        push_log_path: str = "/tmp/slicer_push.jsonl",
        startup_timeout: float = 60.0,
        no_main_window: bool = True,
    ):
        self.slicer_bin = slicer_bin
        self.bootstrap_path = Path(bootstrap_path or _DEFAULT_BOOTSTRAP)
        self.sock_path = sock_path
        self.push_sock_path = push_sock_path
        self.push_log_path = push_log_path
        self.startup_timeout = startup_timeout
        self.no_main_window = no_main_window
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self):
        """Launch Slicer with bootstrap, wait for socket, connect."""
        if os.path.exists(self.sock_path):
            os.remove(self.sock_path)

        env = {
            **os.environ,
            "SLICER_SOCK": self.sock_path,
            "SLICER_PUSH_SOCK": self.push_sock_path,
            "SLICER_PUSH_LOG": self.push_log_path,
            "SLICER_BOOTSTRAP_LOG": "/tmp/slicer_bootstrap.log",
            # Forward display vars for headless X11 (no-op if already set)
            "DISPLAY": os.environ.get("DISPLAY", ":1"),
        }

        args = [str(self.slicer_bin),
                "--python-script", str(self.bootstrap_path),
                "--no-splash"]
        if self.no_main_window:
            args.append("--no-main-window")

        self._proc = subprocess.Popen(args, env=env)

        await self._wait_for_socket()
        self._sock = await self._connect_with_retry()

    async def close(self):
        """Disconnect and terminate the Slicer subprocess."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc:
            self._proc.terminate()
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._proc.wait, 5
                )
            except Exception:
                self._proc.kill()
            self._proc = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.close()

    # ── RPC ─────────────────────────────────────────────────────────────────

    async def run(self, code: str) -> dict:
        """
        Exec `code` inside Slicer and return the response dict.
        Assign __result__ inside code to return a value.
        Raises RuntimeError if Slicer returned an error traceback.
        """
        req = json.dumps({"id": str(uuid.uuid4()), "code": code}).encode() + b"\n"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_rpc, req)

    async def run_checked(self, code: str) -> dict:
        """Like run(), but raises RuntimeError if resp['error'] is not None."""
        resp = await self.run(code)
        if resp.get("error"):
            raise RuntimeError(f"Slicer RPC error:\n{resp['error']}")
        return resp

    def _sync_rpc(self, req: bytes) -> dict:
        self._sock.sendall(req)
        buf = b""
        while b"\n" not in buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("Slicer socket closed unexpectedly")
            buf += chunk
        return json.loads(buf.split(b"\n", 1)[0])

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _wait_for_socket(self):
        """Poll until the socket file appears (created by bootstrap on bind)."""
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if os.path.exists(self.sock_path):
                return
            await asyncio.sleep(0.1)
        raise TimeoutError(
            f"Slicer did not create socket at {self.sock_path} "
            f"within {self.startup_timeout}s. "
            f"Check /tmp/slicer_bootstrap.log for errors."
        )

    async def _connect_with_retry(self, retries: int = 50) -> socket.socket:
        """
        Connect to the Unix socket with retries.

        The socket file appears at bind() but listen() is called immediately after.
        There is a brief window where connect() returns ECONNREFUSED. Retry until
        the server is actually listening.
        """
        loop = asyncio.get_event_loop()
        for _ in range(retries):
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                await loop.run_in_executor(None, sock.connect, self.sock_path)
                return sock
            except ConnectionRefusedError:
                await asyncio.sleep(0.1)
        raise ConnectionError(
            f"Could not connect to {self.sock_path} after {retries} retries"
        )
