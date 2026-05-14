"""
Outbound WebSocket client for agent status/live data updates.

The client reconnects automatically and can be stopped promptly even while it is
waiting inside reconnect backoff.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Callable

try:
    import websockets

    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("[WS] WARNING: websockets not installed. Run: pip install websockets")

from agent import config
from agent.config import INVITE_TOKEN, WS_URL


Observer = Callable[[str, dict], None]


def _safe_error_text(error) -> str:
    return str(error).encode("ascii", "backslashreplace").decode("ascii")


class WSClient:
    def __init__(self, observer: Observer | None = None):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ws = None
        self._queue: asyncio.Queue | None = None
        self._observer = observer
        self._running = False
        self._stop_requested = threading.Event()
        self._stop_async_event: asyncio.Event | None = None

        self.state = "idle"
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self.connected_at: float | None = None
        self.last_event_at: float | None = None
        self.retry_delay_s: int | None = None

    def start(self) -> None:
        if not WS_AVAILABLE:
            self.state = "unavailable"
            self._emit("unavailable", error="Python package 'websockets' is not installed.")
            return
        if self._running or (self._thread and self._thread.is_alive()):
            return

        self._stop_requested.clear()
        self._running = True
        self.state = "starting"
        self._emit("starting", url=WS_URL)
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="WSClient")
        self._thread.start()

    def stop(self) -> None:
        if not self._running and self.state in {"idle", "stopped"}:
            return

        self._running = False
        self._stop_requested.set()
        self.state = "stopping"
        self.retry_delay_s = None
        self._emit("stopping", url=WS_URL)

        if self._loop:
            try:
                if self._stop_async_event is not None:
                    self._loop.call_soon_threadsafe(self._stop_async_event.set)
                if self._queue is not None:
                    self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
            except Exception:
                pass

        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2)

    def send_status(self, state: str, extra: dict | None = None) -> None:
        if not WS_AVAILABLE or not self._loop or not self._queue:
            return
        message = {"type": "status", "state": state, "token": self._auth_token()}
        if extra:
            message.update(extra)
        self._enqueue(message)

    def send_live(self, entries: list[dict]) -> None:
        if not WS_AVAILABLE or not self._loop or not self._queue:
            return
        self._enqueue({"type": "live_data", "entries": entries})

    def _enqueue(self, message: dict) -> None:
        try:
            assert self._loop is not None
            assert self._queue is not None
            self._loop.call_soon_threadsafe(self._queue.put_nowait, json.dumps(message))
        except Exception:
            pass

    def _emit(self, event: str, **payload) -> None:
        now = time.time()
        self.last_event_at = now
        error = payload.get("error")
        if error:
            self.last_error = str(error)
            self.last_error_at = now

        if self._observer:
            try:
                self._observer(event, payload)
            except Exception:
                pass

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue()
        self._stop_async_event = asyncio.Event()
        loop = self._loop

        try:
            self._loop.run_until_complete(self._connect_loop())
        finally:
            self._ws = None
            self._queue = None
            self._stop_async_event = None
            self.connected_at = None
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            if loop is not None and not loop.is_closed():
                try:
                    loop.close()
                except Exception:
                    pass
            self._loop = None
            if self.state != "stopped":
                self.state = "stopped"
                self._emit("stopped", url=WS_URL)

    async def _connect_loop(self) -> None:
        url = f"{WS_URL}?token={self._auth_token()}"
        retry_delay = 2

        while self._running and not self._stop_requested.is_set():
            self.state = "connecting"
            self.retry_delay_s = retry_delay
            self._emit("connecting", url=WS_URL, retry_delay_s=retry_delay)

            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    self.state = "connected"
                    self.connected_at = time.time()
                    self.retry_delay_s = None
                    retry_delay = 2
                    print(f"[WS] Connected to {WS_URL}")
                    self._emit("connected", url=WS_URL)

                    while self._running and not self._stop_requested.is_set():
                        try:
                            assert self._queue is not None
                            message = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                        except asyncio.TimeoutError:
                            continue

                        if message is None:
                            if self._stop_requested.is_set() or not self._running:
                                break
                            continue

                        try:
                            await ws.send(message)
                        except Exception as exc:
                            self.state = "error"
                            self.connected_at = None
                            print(f"[WS] Send error: {_safe_error_text(exc)}")
                            self._emit("send_failed", url=WS_URL, error=str(exc))
                            break

            except Exception as exc:
                self._ws = None
                self.connected_at = None
                if not self._running or self._stop_requested.is_set():
                    break

                if self._is_auth_rejection(exc):
                    # Backend rejected the token. Retrying with the same token
                    # is pointless — stop the loop and let the launcher prompt
                    # the user for a new one via set_agent_token().
                    self.state = "auth_failed"
                    self._running = False
                    print("[WS] Agent token rejected (401)")
                    self._emit("auth_rejected", url=WS_URL, error=str(exc))
                    break

                self.state = "error"
                print(f"[WS] Connection failed: {_safe_error_text(exc)}. Retry in {retry_delay}s")
                self._emit(
                    "connect_failed",
                    url=WS_URL,
                    error=str(exc),
                    retry_delay_s=retry_delay,
                )
                if await self._wait_or_stop(retry_delay):
                    break
                retry_delay = min(retry_delay * 2, 60)
                continue

            self._ws = None
            self.connected_at = None
            if not self._running or self._stop_requested.is_set():
                break

        self._ws = None
        self.connected_at = None
        self.state = "stopped"

    @staticmethod
    def _auth_token() -> str:
        return config.get_agent_secret_token() or INVITE_TOKEN

    @staticmethod
    def _is_auth_rejection(exc: Exception) -> bool:
        """Best-effort detection of an HTTP 401 from the websockets handshake."""
        for attr in ("status_code", "code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int) and value == 401:
                return True
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if isinstance(status, int) and status == 401:
            return True
        message = str(exc)
        return "401" in message and ("Unauthorized" in message or "unauthorized" in message)

    async def _wait_or_stop(self, timeout_s: int) -> bool:
        if self._stop_async_event is None:
            await asyncio.sleep(timeout_s)
            return False

        try:
            await asyncio.wait_for(self._stop_async_event.wait(), timeout=timeout_s)
            return True
        except asyncio.TimeoutError:
            return False
