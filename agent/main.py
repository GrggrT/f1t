"""
Main F1 agent runtime.

Starts UDP telemetry, websocket status sync, uploads, and the optional overlay.
"""
from __future__ import annotations

import asyncio
import copy
import threading
import time
from typing import Callable

import agent.config as agent_config
from agent.auto_scan import AutoScanner
from agent.overlay_server import OverlayServer
from agent.packet_parser import (
    extract_car_damage,
    extract_car_status,
    extract_car_telemetry,
    extract_event,
    extract_final_classification,
    extract_lap_data,
    extract_lap_positions,
    extract_motion,
    extract_participants,
    extract_session_history,
    extract_session_info,
    parse_packet,
)
from agent.raw_logger import RawLogger
from agent.personal_session_sync import sync_personal_session
from agent.state_machine import AgentState, StateMachine
from agent.telemetry_buffer import TelemetryBuffer
from agent import telemetry_delivery
from agent.udp_listener import (
    PACKET_ID_CAR_DAMAGE,
    PACKET_ID_CAR_STATUS,
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_EVENT,
    PACKET_ID_FINAL_CLASSIF,
    PACKET_ID_LAP_DATA,
    PACKET_ID_LAP_POSITIONS,
    PACKET_ID_MOTION,
    PACKET_ID_PARTICIPANTS,
    PACKET_ID_SESSION,
    PACKET_ID_SESSION_HISTORY,
    UDPListener,
)
from agent.uploader import build_race_payload, retry_pending_uploads, upload_race
from agent.ws_client import WSClient
from shared.f1_mappings import QUALI_SESSION_TYPES, RACE_SESSION_TYPES, get_track_name


Observer = Callable[[str, str, dict], None]


class F1Agent:
    def __init__(self, observer: Observer | None = None):
        self._observer = observer
        self._lock = threading.RLock()
        self._running = False

        self.sm = StateMachine(on_change=self._on_state_change)
        self.ws = WSClient(observer=self._make_observer("ws"))
        self.raw_log = RawLogger()
        self.udp = UDPListener(callback=self._on_packet, observer=self._make_observer("udp"))

        self._session_uid: int = 0
        self._packet_format: int = 2025
        self._track_id: int | None = None
        self._session_type: int | None = None
        self._session_info: dict = {}
        self._participants: list[dict] = []
        self._events: list[dict] = []
        self._fastest_lap_vidx: int | None = None
        self._final_classification: list[dict] = []
        self._uploaded_uids: set[int] = set()
        self._uploading_uids: set[int] = set()
        self._syncing_personal_session_uids: set[int] = set()

        self._live_data: dict[int, dict] = {}
        self._live_last_sent: float = 0.0
        self._telem = TelemetryBuffer()
        self._scanner = AutoScanner()

        self._overlay = OverlayServer(observer=self._make_observer("overlay"))
        self._overlay_enabled = False
        self._tray = None

    def _emit(self, source: str, event: str, **payload) -> None:
        if not self._observer:
            return
        try:
            self._observer(source, event, payload)
        except Exception:
            pass

    def _make_observer(self, source: str):
        def handler(event: str, payload: dict | None = None) -> None:
            self._emit(source, event, **(payload or {}))

        return handler

    def start_runtime(self, *, retry_cached_uploads: bool = True) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        print("[AGENT] Starting F1 League Agent")
        self._emit("agent", "run_started")

        if retry_cached_uploads:
            asyncio.run(retry_pending_uploads(observer=self._make_observer("upload")))
            asyncio.run(telemetry_delivery.retry_pending(observer=self._make_observer("telemetry")))

        if self._overlay_enabled and not self._overlay._running:
            self._overlay.start()

        self.ws.start()
        self.udp.start()
        self._send_status()

    def shutdown(self, *, stop_overlay: bool = True) -> None:
        with self._lock:
            already_running = self._running
            self._running = False

        if already_running:
            self._emit("agent", "shutdown_started")
        self.udp.stop()
        self.ws.stop()
        if stop_overlay:
            self._overlay.stop()

        with self._lock:
            self.raw_log.stop()
            self._telem.reset()
            self._live_data = {}
            self._live_last_sent = 0.0

        if already_running:
            self._emit("agent", "shutdown_completed")
            print("[AGENT] Stopped")

    def run(self) -> None:
        self.start_runtime(retry_cached_uploads=True)
        self._run_tray()

    def _run_tray(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw

            def make_icon(color: str = "gray") -> Image.Image:
                img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse([8, 8, 56, 56], fill=color)
                return img

            color_map = {
                AgentState.IDLE: "gray",
                AgentState.WAITING: "yellow",
                AgentState.QUALIFYING: "blue",
                AgentState.RACE: "green",
                AgentState.FINISHED: "orange",
                AgentState.UPLOADED: "lime",
            }

            def on_quit(icon, item):
                icon.stop()
                self.shutdown()

            icon = pystray.Icon(
                "f1league",
                make_icon("gray"),
                "F1 League Agent",
                menu=pystray.Menu(
                    pystray.MenuItem(lambda text: self.sm.label(), None, enabled=False),
                    pystray.MenuItem("Quit", on_quit),
                ),
            )

            def update_icon(new_state: AgentState):
                color = color_map.get(new_state, "gray")
                icon.icon = make_icon(color)
                icon.title = f"F1 League - {self.sm.label()}"

            self.sm._on_change = lambda state: (self._on_state_change(state), update_icon(state))
            self._tray = icon
            icon.run()

        except ImportError:
            print("[TRAY] pystray/pillow not available - running in console mode")
            print("[TRAY] Press Ctrl+C to stop")
            try:
                while self._running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                self.shutdown()

    def _on_packet(self, packet_id: int, session_uid: int, packet_format: int, data: bytes) -> None:
        parsed = parse_packet(packet_id, packet_format, data)

        with self._lock:
            self._packet_format = packet_format

            if packet_id != PACKET_ID_SESSION and self._session_uid and session_uid != self._session_uid:
                if packet_id == PACKET_ID_FINAL_CLASSIF and (
                    session_uid in self._uploading_uids or session_uid in self._uploaded_uids
                ):
                    return

                self._emit(
                    "agent",
                    "stale_packet_ignored",
                    packet_id=packet_id,
                    session_uid=session_uid,
                    active_session_uid=self._session_uid,
                )
                return

            if self.sm.state in (AgentState.WAITING, AgentState.QUALIFYING, AgentState.RACE):
                self.raw_log.write(data)

            if packet_id == PACKET_ID_SESSION:
                self._handle_session_locked(session_uid, parsed)
            elif packet_id == PACKET_ID_PARTICIPANTS:
                self._handle_participants_locked(parsed)
            elif packet_id == PACKET_ID_EVENT:
                self._handle_event_locked(session_uid, parsed)
            elif packet_id == PACKET_ID_FINAL_CLASSIF:
                self._handle_final_classification_locked(session_uid, parsed)
            elif self.sm.state == AgentState.RACE and self._telem._running:
                self._handle_race_packet_locked(packet_id, parsed)

    def _handle_race_packet_locked(self, packet_id: int, parsed: dict | None) -> None:
        if packet_id == PACKET_ID_MOTION:
            for motion in extract_motion(parsed or {}):
                self._telem.update_motion(
                    motion["vehicle_index"],
                    motion["world_x"],
                    motion["world_z"],
                )

        elif packet_id == PACKET_ID_CAR_TELEMETRY:
            for telemetry in extract_car_telemetry(parsed or {}):
                self._telem.update_telemetry(
                    telemetry["vehicle_index"],
                    telemetry["speed"],
                    telemetry["throttle"],
                    telemetry["brake"],
                    telemetry["gear"],
                    telemetry["drs"],
                    telemetry["steer"],
                )
                if self._overlay_enabled and telemetry["vehicle_index"] == 0:
                    self._overlay.push_car_telemetry(
                        0,
                        {
                            "speed": telemetry["speed"],
                            "throttle": telemetry["throttle"],
                            "brake": telemetry["brake"],
                            "gear": telemetry["gear"],
                            "drs": telemetry["drs"],
                            "tyre_temps": telemetry.get("tyres_surface_temp"),
                        },
                    )

        elif packet_id == PACKET_ID_CAR_STATUS:
            for car_status in extract_car_status(parsed or {}):
                self._telem.update_car_status(
                    car_status["vehicle_index"],
                    car_status["ers_deploy"],
                    car_status["ers_store"],
                    car_status["fuel_in_tank"],
                    car_status["fuel_remaining_laps"],
                )
                vidx = car_status["vehicle_index"]
                entry = self._live_data.setdefault(vidx, {})
                entry["tyre"] = car_status["visual_tyre"]
                entry["drs_active"] = car_status["drs_allowed"] == 1
                if self._overlay_enabled and vidx == 0:
                    max_ers = 4_000_000
                    self._overlay.push_car_telemetry(
                        0,
                        {
                            "ers_pct": car_status["ers_store"] / max_ers if max_ers else 0,
                            "fuel_laps": car_status["fuel_remaining_laps"],
                        },
                    )

        elif packet_id == PACKET_ID_CAR_DAMAGE:
            for damage in extract_car_damage(parsed or {}):
                self._telem.update_car_damage(damage["vehicle_index"], damage["tyres_wear"])
                if self._overlay_enabled and damage["vehicle_index"] == 0:
                    self._overlay.push_car_telemetry(0, {"tyre_wear": damage["tyres_wear"]})

        elif packet_id == PACKET_ID_SESSION_HISTORY:
            history = extract_session_history(parsed or {})
            if history:
                self._telem.update_session_history(history["vehicle_index"], history)

        elif packet_id == PACKET_ID_LAP_POSITIONS:
            for lap_position in extract_lap_positions(parsed or {}):
                vidx = lap_position["vehicle_index"]
                entry = self._live_data.setdefault(vidx, {})
                if lap_position["position"] > 0:
                    entry["position"] = lap_position["position"]

        elif packet_id == PACKET_ID_LAP_DATA:
            for lap in extract_lap_data(parsed or {}):
                self._telem.update_lap(
                    lap["vehicle_index"],
                    lap["lap_number"],
                    lap["lap_distance"],
                    lap["session_time"],
                    lap["last_lap_ms"] or None,
                )
                vidx = lap["vehicle_index"]
                entry = self._live_data.setdefault(vidx, {})
                entry.update(
                    position=lap["car_position"],
                    lap=lap["lap_number"],
                    last_lap_ms=lap["last_lap_ms"] or None,
                    best_lap_ms=lap["best_lap_ms"] or None,
                    pit_stops=lap["num_pit_stops"],
                )

            now = time.time()
            if now - self._live_last_sent >= 2.0:
                self._live_last_sent = now
                self._send_live_snapshot()

    def _handle_session_locked(self, session_uid: int, parsed: dict | None) -> None:
        info = extract_session_info(parsed) if parsed else {}
        track_id = info.get("track_id")
        session_type = info.get("session_type")

        if session_uid != self._session_uid:
            self._start_new_session_locked(
                session_uid,
                packet_format=self._packet_format,
                reason="session_uid_changed",
            )

        self._track_id = track_id
        self._session_type = session_type

        if self._scanner.active:
            self._scanner.process_session(track_id)

        if info.get("weather") is not None:
            if "weather_start" not in self._session_info:
                self._session_info["weather_start"] = info["weather"]
            self._session_info["weather_end"] = info["weather"]

        self._session_info.update(
            {
                "total_laps": info.get("total_laps"),
                "air_temp": info.get("air_temp"),
                "track_temp": info.get("track_temp"),
            }
        )

        if self._overlay_enabled:
            self._overlay.push_session(
                {
                    "track_name": get_track_name(track_id) if track_id is not None else None,
                    "total_laps": info.get("total_laps"),
                    "weather": info.get("weather"),
                    "air_temp": info.get("air_temp"),
                }
            )

        current_state = self.sm.state
        if current_state == AgentState.IDLE:
            if track_id is not None:
                track_name = get_track_name(track_id)
                print(f"[AGENT] Track detected: {track_name} (type={session_type})")
                self._emit(
                    "agent",
                    "track_detected",
                    track_name=track_name,
                    session_type=session_type,
                )
                if self.sm.transition(AgentState.WAITING, reason="track_detected"):
                    self._send_status(track=track_name)

        elif current_state == AgentState.WAITING:
            if session_type in QUALI_SESSION_TYPES:
                if self.sm.transition(AgentState.QUALIFYING, reason="session_type_qualifying"):
                    self._send_status()
            elif session_type in RACE_SESSION_TYPES:
                self._enter_race_locked(reason="session_type_race")

        elif current_state == AgentState.QUALIFYING:
            if session_type in RACE_SESSION_TYPES:
                self._enter_race_locked(reason="qualifying_to_race")

    def _handle_participants_locked(self, parsed: dict | None) -> None:
        if parsed is None:
            return

        participants = extract_participants(parsed)
        if participants:
            self._participants = participants
            human_count = sum(1 for participant in participants if participant.get("m_aiControlled") == 0)
            print(f"[AGENT] Participants updated: {len(participants)} total, {human_count} humans")
            if self._scanner.active:
                self._scanner.process_participants(participants)
                self._scanner.mark_done()

    def _handle_event_locked(self, session_uid: int, parsed: dict | None) -> None:
        if not self._session_uid or session_uid != self._session_uid:
            return

        event = extract_event(parsed) if parsed else None
        if not event:
            return

        code = event.get("code", "")
        data = event.get("data", {})
        print(f"[EVENT] {code}: {data}")

        if code == "FTLP":
            vidx = data.get("vehicleIdx") if isinstance(data, dict) else None
            if vidx is not None:
                self._fastest_lap_vidx = vidx

        if self.sm.state in (AgentState.RACE, AgentState.QUALIFYING):
            self._events.append(
                {
                    "event_code": code,
                    "event_data": data if isinstance(data, dict) else {},
                    "lap_number": None,
                    "session_time": None,
                }
            )

    def _handle_final_classification_locked(self, session_uid: int, parsed: dict | None) -> None:
        if not self._session_uid or session_uid != self._session_uid:
            self._emit(
                "agent",
                "stale_final_classification_ignored",
                session_uid=session_uid,
                active_session_uid=self._session_uid,
            )
            return
        if session_uid in self._uploaded_uids or session_uid in self._uploading_uids:
            self._emit("agent", "duplicate_final_classification_ignored", session_uid=session_uid)
            return
        if self.sm.state not in (AgentState.RACE, AgentState.QUALIFYING, AgentState.WAITING):
            return

        classification = extract_final_classification(parsed) if parsed else []
        if not classification:
            print("[AGENT] Empty FinalClassification, skipping")
            return

        self._final_classification = classification
        self._finalize_finished_session_locked(session_uid)
        self._emit(
            "agent",
            "final_classification_received",
            session_uid=session_uid,
            classification_count=len(classification),
        )
        self.sm.transition(AgentState.FINISHED, reason="final_classification_received")
        self._send_status()

        payload = self._build_upload_payload_locked(session_uid)
        if payload is None:
            self._emit(
                "upload",
                "missing_participants",
                session_uid=session_uid,
                error="No participants data available for upload.",
            )
            print("[AGENT] No participants data, cannot upload")
            self._reset_session_if_current(session_uid, reason="missing_participants")
            return

        self._uploading_uids.add(session_uid)
        self._start_upload_worker(session_uid, payload)

    def _build_upload_payload_locked(self, session_uid: int) -> dict | None:
        if not self._participants:
            return None

        return build_race_payload(
            session_uid=session_uid,
            packet_format=self._packet_format,
            track_id=self._track_id or 0,
            session_info=copy.deepcopy(self._session_info),
            participants=copy.deepcopy(self._participants),
            classification=copy.deepcopy(self._final_classification),
            events=copy.deepcopy(self._events),
            fastest_lap_vehicle_idx=self._fastest_lap_vidx,
        )

    def _start_upload_worker(self, session_uid: int, payload: dict) -> None:
        upload_thread = threading.Thread(
            target=self._upload_race,
            args=(session_uid, payload),
            daemon=True,
            name=f"Upload-{session_uid}",
        )
        upload_thread.start()

    def _upload_race(self, session_uid: int, payload: dict) -> None:
        success, race_id = upload_race(payload, observer=self._make_observer("upload"))

        with self._lock:
            self._uploading_uids.discard(session_uid)

            if success:
                self._uploaded_uids.add(session_uid)
                if self._session_uid == session_uid:
                    self.sm.transition(AgentState.UPLOADED, reason="upload_succeeded")
                    self._send_status()
            else:
                if self._session_uid == session_uid:
                    self._emit(
                        "upload",
                        "cached_for_later",
                        session_uid=session_uid,
                        error="Upload failed; results remain cached locally.",
                    )

        if success:
            print(f"[AGENT] Race {session_uid} uploaded successfully")
            if race_id:
                telemetry_delivery.flush_pending(
                    session_uid,
                    race_id=race_id,
                    observer=self._make_observer("telemetry"),
                )
            else:
                self._emit(
                    "telemetry",
                    "blocked_no_race_id",
                    session_uid=session_uid,
                    error="Upload succeeded without race_id; telemetry snapshot stays cached locally.",
                )
            time.sleep(0.75)
        else:
            print("[AGENT] Upload failed, data cached locally")

        self._reset_session_if_current(
            session_uid,
            reason="upload_complete" if success else "upload_cached",
        )

    def _finalize_finished_session_locked(self, session_uid: int) -> None:
        raw_path = self.raw_log.stop()
        snapshot = self._telem.stop_and_snapshot()
        if snapshot.has_data():
            telemetry_delivery.save_snapshot(session_uid, snapshot)
            if agent_config.AGENT_MODE == "personal":
                self._start_personal_session_sync(session_uid, snapshot)
        else:
            telemetry_delivery.remove(session_uid)
        self._emit(
            "agent",
            "session_capture_finalized",
            session_uid=session_uid,
            raw_log_path=str(raw_path) if raw_path else None,
            telemetry_snapshot=snapshot.has_data(),
        )

    def _start_personal_session_sync(self, session_uid: int, snapshot) -> None:
        if session_uid in self._syncing_personal_session_uids:
            return

        self._syncing_personal_session_uids.add(session_uid)
        worker = threading.Thread(
            target=self._sync_personal_session,
            args=(
                session_uid,
                snapshot,
                self._track_id,
                self._session_type,
                copy.deepcopy(self._participants),
                copy.deepcopy(self._final_classification),
            ),
            daemon=True,
            name=f"PersonalSession-{session_uid}",
        )
        worker.start()

    def _sync_personal_session(
        self,
        session_uid: int,
        snapshot,
        track_id: int | None,
        session_type: int | None,
        participants: list[dict],
        classification: list[dict],
    ) -> None:
        try:
            sync_personal_session(
                session_uid,
                snapshot,
                track_id=track_id,
                session_type=session_type,
                participants=participants,
                classification=classification,
                observer=self._make_observer("personal_session"),
            )
        finally:
            with self._lock:
                self._syncing_personal_session_uids.discard(session_uid)

    def _enter_race_locked(self, *, reason: str) -> None:
        transitioned = self.sm.transition(AgentState.RACE, reason=reason)
        if transitioned or not self._telem._running:
            self.raw_log.start_session(self._track_id or -1)
            self._telem.start_collecting()
            self._send_status()

    def _start_new_session_locked(self, session_uid: int, packet_format: int = 2025, reason: str = "new_session") -> None:
        previous_uid = self._session_uid
        previous_state = self.sm.state
        if previous_uid == session_uid:
            return

        if previous_uid:
            self._emit(
                "agent",
                "session_rollover",
                previous_session_uid=previous_uid,
                session_uid=session_uid,
                previous_state=previous_state.value,
            )

        self.raw_log.stop()
        self._telem.reset()

        self._session_uid = session_uid
        self._packet_format = packet_format
        self._track_id = None
        self._session_type = None
        self._session_info = {}
        self._participants = []
        self._events = []
        self._fastest_lap_vidx = None
        self._final_classification = []
        self._live_data = {}
        self._live_last_sent = 0.0

        if previous_state != AgentState.IDLE:
            self.sm.reset(reason=f"session_rollover:{reason}")

        print(f"[AGENT] New session: uid={session_uid}")
        self._emit("agent", "session_started", session_uid=session_uid, packet_format=packet_format)

    def _reset_session_if_current(self, session_uid: int, *, reason: str) -> None:
        with self._lock:
            if self._session_uid != session_uid:
                return
            if self.sm.state not in (AgentState.FINISHED, AgentState.UPLOADED):
                return
            self._reset_session_locked(reason=reason)

    def _reset_session_locked(self, *, reason: str) -> None:
        self.raw_log.stop()
        self._telem.reset()
        self._session_uid = 0
        self._packet_format = 2025
        self._track_id = None
        self._session_type = None
        self._session_info = {}
        self._participants = []
        self._events = []
        self._fastest_lap_vidx = None
        self._final_classification = []
        self._live_data = {}
        self._live_last_sent = 0.0

        self.sm.reset(reason=reason)
        self._send_status()
        self._emit("agent", "session_reset", reason=reason)
        print("[AGENT] Ready for next race")

    def _send_live_snapshot(self) -> None:
        if not self._participants:
            return

        from shared.f1_mappings import get_driver, get_team

        parts_map = {participant["vehicle_index"]: participant for participant in self._participants}
        entries = []
        for vidx, live in self._live_data.items():
            participant = parts_map.get(vidx, {})
            team = get_team(participant.get("m_teamId", 255))
            driver = get_driver(participant.get("m_driverId", 255))
            is_human = participant.get("m_aiControlled", 1) == 0
            entries.append(
                {
                    "vehicle_index": vidx,
                    "position": live.get("position", 99),
                    "driver_name": driver.get("name", f"Car {vidx}"),
                    "team_name": team.get("name", "Unknown"),
                    "team_color": team.get("color", "#888888"),
                    "is_human": is_human,
                    "lap": live.get("lap", 0),
                    "last_lap_ms": live.get("last_lap_ms"),
                    "best_lap_ms": live.get("best_lap_ms"),
                    "gap": "",
                    "tyre": live.get("tyre", ""),
                    "pit_stops": live.get("pit_stops", 0),
                    "drs_active": live.get("drs_active", False),
                }
            )

        entries.sort(key=lambda entry: entry["position"])
        self.ws.send_live(entries)
        if self._overlay_enabled:
            self._overlay.push_timing(entries)

    def _on_state_change(self, new_state: AgentState) -> None:
        self._emit("agent", "state_changed", state=new_state.value, label=self.sm.label())
        self._send_status()

    def _send_status(self, **extra) -> None:
        track_id = self._track_id
        self.ws.send_status(
            state=self.sm.state.value,
            extra={
                "track_id": track_id,
                "track_name": get_track_name(track_id) if track_id is not None else None,
                "label": self.sm.label(),
                **extra,
            },
        )


def main():
    agent = F1Agent()
    agent.run()


if __name__ == "__main__":
    main()
