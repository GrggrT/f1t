"""
UDP listener for F1 telemetry packets.

Runs in its own thread and reports bind/runtime issues through an observer hook.
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Callable

from agent.config import UDP_HOST, UDP_PORT


HEADER_FORMAT = "<HBBBBBQfIIBB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

PACKET_ID_MOTION = 0
PACKET_ID_SESSION = 1
PACKET_ID_LAP_DATA = 2
PACKET_ID_EVENT = 3
PACKET_ID_PARTICIPANTS = 4
PACKET_ID_CAR_TELEMETRY = 6
PACKET_ID_CAR_STATUS = 7
PACKET_ID_CAR_DAMAGE = 8
PACKET_ID_SESSION_HISTORY = 10
PACKET_ID_FINAL_CLASSIF = 11
PACKET_ID_LAP_POSITIONS = 12


Observer = Callable[[str, dict], None]


def _safe_error_text(error) -> str:
    return str(error).encode("ascii", "backslashreplace").decode("ascii")


class UDPListener(threading.Thread):
    """
    callback(packet_id: int, session_uid: int, packet_format: int, data: bytes)
    """

    def __init__(
        self,
        callback: Callable[[int, int, int, bytes], None],
        observer: Observer | None = None,
    ):
        super().__init__(daemon=True, name="UDPListener")
        self._callback = callback
        self._observer = observer
        self._stop_event = threading.Event()
        self._sock: socket.socket | None = None

        self.state = "idle"
        self.packets_received = 0
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self.last_packet_at: float | None = None

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

    def run(self) -> None:
        self.state = "starting"
        self._emit("starting", host=UDP_HOST, port=UDP_PORT)

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((UDP_HOST, UDP_PORT))
            self._sock.settimeout(1.0)
        except Exception as exc:
            self.state = "error"
            self._emit("bind_failed", host=UDP_HOST, port=UDP_PORT, error=str(exc))
            print(f"[UDP] Bind error on {UDP_HOST}:{UDP_PORT}: {_safe_error_text(exc)}")
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
            return

        self.state = "listening"
        self._emit("listening", host=UDP_HOST, port=UDP_PORT)
        print(f"[UDP] Listening on {UDP_HOST}:{UDP_PORT}")

        while not self._stop_event.is_set():
            try:
                assert self._sock is not None
                data, _ = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                if self._stop_event.is_set():
                    break
                self.state = "error"
                self._emit("receive_failed", host=UDP_HOST, port=UDP_PORT, error=str(exc))
                print(f"[UDP] Receive error: {_safe_error_text(exc)}")
                time.sleep(0.1)
                continue
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                self.state = "error"
                self._emit("receive_failed", host=UDP_HOST, port=UDP_PORT, error=str(exc))
                print(f"[UDP] Receive error: {_safe_error_text(exc)}")
                time.sleep(0.1)
                continue

            if len(data) < HEADER_SIZE:
                continue

            try:
                header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
                packet_format = header[0]
                packet_id = header[5]
                session_uid = header[6]
            except struct.error:
                continue

            self.packets_received += 1
            self.last_packet_at = time.time()
            if self.packets_received == 1:
                self._emit(
                    "first_packet",
                    host=UDP_HOST,
                    port=UDP_PORT,
                    packets_received=self.packets_received,
                )

            try:
                self._callback(packet_id, session_uid, packet_format, data)
            except Exception as exc:
                self.state = "error"
                self._emit(
                    "callback_failed",
                    host=UDP_HOST,
                    port=UDP_PORT,
                    packet_id=packet_id,
                    error=str(exc),
                )
                print(f"[UDP] Callback error (packet_id={packet_id}): {_safe_error_text(exc)}")
                continue

            if self.state != "listening":
                self.state = "listening"
                self._emit(
                    "listening",
                    host=UDP_HOST,
                    port=UDP_PORT,
                    recovered=True,
                    packets_received=self.packets_received,
                )

        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self.state = "stopped"
        self._emit("stopped", host=UDP_HOST, port=UDP_PORT, packets_received=self.packets_received)
        print("[UDP] Stopped")

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if threading.current_thread() is not self and self.is_alive():
            self.join(timeout=2)
