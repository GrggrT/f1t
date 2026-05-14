"""
Local overlay server that serves the browser HUD and broadcasts live data via WebSocket.
Runs on localhost:8080/8081 and reports startup/runtime issues to an observer hook.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Callable

try:
    import websockets
    from websockets.server import serve as ws_serve

    WS_OK = True
except ImportError:
    WS_OK = False

OVERLAY_DIR = Path(__file__).parent / "overlay"
OVERLAY_PORT = 8080
WS_PORT = 8081
Observer = Callable[[str, dict], None]


def _safe_error_text(error) -> str:
    return str(error).encode("ascii", "backslashreplace").decode("ascii")


class OverlayServer:
    """Runs HTTP (overlay page) + WebSocket (live data) on localhost."""

    def __init__(self, observer: Observer | None = None):
        self._ws_clients: set = set()
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._http_thread: threading.Thread | None = None
        self._observer = observer

        self.state = "idle"
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self.http_ready = False
        self.ws_ready = False

        # Latest state for new clients.
        self._latest_timing: list[dict] = []
        self._latest_car_data: dict[int, dict] = {}
        self._latest_session: dict = {}
        self._latest_delta: dict[int, dict] = {}

    def start(self):
        if self._running:
            return
        if not WS_OK:
            self.state = "error"
            self._emit("unavailable", error="Python package 'websockets' is not installed.")
            print("[OVERLAY] websockets not available, overlay disabled")
            return

        self._running = True
        self.state = "starting"
        self.http_ready = False
        self.ws_ready = False
        self._emit("starting", http_port=OVERLAY_PORT, ws_port=WS_PORT)

        self._http_thread = threading.Thread(target=self._run_http, daemon=True, name="OverlayHTTP")
        self._http_thread.start()

        self._thread = threading.Thread(target=self._run_ws, daemon=True, name="OverlayWS")
        self._thread.start()

        print(f"[OVERLAY] Overlay at http://localhost:{OVERLAY_PORT}/overlay.html")
        print(f"[OVERLAY] WebSocket at ws://localhost:{WS_PORT}")

    def stop(self):
        if not self._running and self.state in {"idle", "stopped"}:
            return
        self._running = False
        self.state = "stopping"
        self._emit("stopping", http_port=OVERLAY_PORT, ws_port=WS_PORT)
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(lambda: None)
            except Exception:
                pass

    def push_timing(self, entries: list[dict]):
        self._latest_timing = entries
        self._broadcast({"type": "timing", "entries": entries})

    def push_car_telemetry(self, vidx: int, data: dict):
        self._latest_car_data[vidx] = data
        self._broadcast({"type": "car", "vidx": vidx, **data})

    def push_session(self, data: dict):
        self._latest_session = data
        self._broadcast({"type": "session", **data})

    def push_lap_delta(self, vidx: int, current_ms: float, best_ms: float, delta_ms: float):
        payload = {
            "type": "delta",
            "vidx": vidx,
            "current_ms": current_ms,
            "best_ms": best_ms,
            "delta_ms": delta_ms,
        }
        self._latest_delta[vidx] = payload
        self._broadcast(payload)

    def _emit(self, event: str, **payload) -> None:
        error = payload.get("error")
        if error:
            self.last_error = str(error)
            self.last_error_at = time.time()

        if self._observer:
            try:
                self._observer(event, payload)
            except Exception:
                pass

    def _set_running_if_ready(self) -> None:
        if self.http_ready and self.ws_ready:
            self.state = "running"
            self._emit("running", http_port=OVERLAY_PORT, ws_port=WS_PORT)

    def _set_stopped_if_done(self) -> None:
        if not self._running and not self.http_ready and not self.ws_ready:
            self.state = "stopped"
            self._emit("stopped", http_port=OVERLAY_PORT, ws_port=WS_PORT)

    def _broadcast(self, msg: dict):
        if not self._loop or not self._ws_clients:
            return
        text = json.dumps(msg)
        asyncio.run_coroutine_threadsafe(self._send_all(text), self._loop)

    async def _send_all(self, text: str):
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send(text)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def _run_http(self):
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self_, *args, **kwargs):
                super().__init__(*args, directory=str(OVERLAY_DIR), **kwargs)

            def log_message(self_, format, *args):
                pass

        server = None
        try:
            server = HTTPServer(("127.0.0.1", OVERLAY_PORT), Handler)
            server.timeout = 0.5
            self.http_ready = True
            self._emit("http_ready", http_port=OVERLAY_PORT)
            self._set_running_if_ready()
            while self._running:
                server.handle_request()
        except Exception as exc:
            self.http_ready = False
            self.state = "error"
            self._emit("http_error", http_port=OVERLAY_PORT, error=str(exc))
            print(f"[OVERLAY] HTTP error: {_safe_error_text(exc)}")
        finally:
            self.http_ready = False
            if server is not None:
                try:
                    server.server_close()
                except Exception:
                    pass
            self._set_stopped_if_done()

    def _run_ws(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ws_main())
        except Exception as exc:
            self.ws_ready = False
            self.state = "error"
            self._emit("ws_error", ws_port=WS_PORT, error=str(exc))
            print(f"[OVERLAY] WS error: {_safe_error_text(exc)}")
        finally:
            self._ws_clients.clear()
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None
            self.ws_ready = False
            self._set_stopped_if_done()

    async def _ws_main(self):
        async def handler(ws):
            self._ws_clients.add(ws)
            self._emit("client_connected", clients=len(self._ws_clients))
            if self._latest_session:
                await ws.send(json.dumps({"type": "session", **self._latest_session}))
            if self._latest_timing:
                await ws.send(json.dumps({"type": "timing", "entries": self._latest_timing}))
            for vidx, data in self._latest_car_data.items():
                await ws.send(json.dumps({"type": "car", "vidx": vidx, **data}))
            for payload in self._latest_delta.values():
                await ws.send(json.dumps(payload))
            try:
                async for _ in ws:
                    pass
            finally:
                self._ws_clients.discard(ws)
                self._emit("client_disconnected", clients=len(self._ws_clients))

        async with ws_serve(handler, "127.0.0.1", WS_PORT):
            self.ws_ready = True
            self._emit("ws_ready", ws_port=WS_PORT)
            self._set_running_if_ready()
            while self._running:
                await asyncio.sleep(0.5)
