"""
push_listener.py — Agent-side listener for Slicer's push socket.

Slicer pushes newline-delimited JSON events at any time:
  {"type": "vtk_warning",   "text": "...", "ts": 1234567890.123}
  {"type": "vtk_error",     "text": "...", "ts": ...}
  {"type": "vtk_text",      "text": "...", "ts": ...}
  {"type": "python_error",  "text": "...", "ts": ...}
  {"type": "stdout",        "text": "...", "ts": ...}
  {"type": "mrml_event",    "event": "NodeAdded", "node_id": "...", "node_class": "...", "node_name": "...", "ts": ...}

Usage (sync):
    with PushListener() as pl:
        for event in pl.events():
            print(event)

Usage (async):
    async with PushListener() as pl:
        async for event in pl.aevents():
            print(event)

Usage (background thread, non-blocking):
    pl = PushListener()
    pl.connect()
    pl.start_background(callback=lambda e: print(e))
    # ... do other work ...
    pl.stop_background()
    pl.close()
"""
import asyncio
import json
import socket
import threading

PUSH_SOCK_PATH = "/tmp/slicer_agent_push.sock"


class PushListener:
    def __init__(self, push_sock_path: str = PUSH_SOCK_PATH):
        self.push_sock_path = push_sock_path
        self._sock: socket.socket | None = None
        self._bg_thread: threading.Thread | None = None
        self._stop_bg = threading.Event()

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(self.push_sock_path)

    def close(self):
        self.stop_background()
        if self._sock:
            self._sock.close()
            self._sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    async def __aenter__(self):
        self.connect()
        return self

    async def __aexit__(self, *_):
        self.close()

    # ── Sync generator ────────────────────────────────────────────────────────

    def events(self):
        """Blocking generator — yields event dicts until socket closes."""
        buf = b""
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass

    # ── Async generator ───────────────────────────────────────────────────────

    async def aevents(self):
        """Async generator — yields event dicts until socket closes."""
        loop = asyncio.get_event_loop()
        buf = b""
        while True:
            chunk = await loop.run_in_executor(None, self._sock.recv, 4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass

    # ── Background thread ─────────────────────────────────────────────────────

    def start_background(self, callback):
        """
        Start a background thread that calls callback(event) for each event.
        Non-blocking — returns immediately.
        """
        self._stop_bg.clear()

        def _run():
            for event in self.events():
                if self._stop_bg.is_set():
                    break
                try:
                    callback(event)
                except Exception:
                    pass

        self._bg_thread = threading.Thread(target=_run, daemon=True)
        self._bg_thread.start()

    def stop_background(self):
        if self._bg_thread:
            self._stop_bg.set()
            self._bg_thread = None
