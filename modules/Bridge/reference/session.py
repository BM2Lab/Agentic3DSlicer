# slicer/session.py
import asyncio, json, os, socket, subprocess, uuid
from pathlib import Path

class SlicerSession:
    def __init__(self, slicer_bin: str, sock_path: str = "/tmp/slicer_agent.sock"):
        self.slicer_bin = slicer_bin
        self.sock_path = sock_path
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None

    async def start(self):
        bootstrap = Path(__file__).parent / "bootstrap.py"
        self._proc = subprocess.Popen([
            self.slicer_bin,
            "--python-script", str(bootstrap),
            "--no-splash", "--no-main-window",   # headless
        ], env={**os.environ, "SLICER_SOCK": self.sock_path})
        await self._wait_ready()            # poll until socket file appears
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(self.sock_path)

    async def exec(self, code: str) -> dict:
        req = json.dumps({"id": str(uuid.uuid4()), "code": code}).encode() + b"\n"
        loop = asyncio.get_event_loop()
        # offload blocking send/recv to thread pool — keeps agent loop async
        return await loop.run_in_executor(None, self._sync_rpc, req)

    def _sync_rpc(self, req: bytes) -> dict:
        self._sock.sendall(req)
        buf = b""
        while not buf.endswith(b"\n"):
            buf += self._sock.recv(4096)
        return json.loads(buf.strip())

    async def _wait_ready(self, timeout=30):
        for _ in range(timeout * 10):
            if os.path.exists(self.sock_path):
                return
            await asyncio.sleep(0.1)
        raise TimeoutError("Slicer did not start in time")

    async def close(self):
        if self._sock:
            self._sock.close()
        if self._proc:
            self._proc.terminate()