from __future__ import annotations

import argparse
import ctypes
import json
import struct
import tempfile
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import f1.packets as f1_packets

from agent import telemetry_delivery
from agent.main import F1Agent
from agent.packet_parser import (
    F1_PACKETS_API,
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
from agent.raw_logger import replay_log
from agent.udp_listener import (
    HEADER_FORMAT,
    HEADER_SIZE,
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
)


PACKET_ID_CAR_SETUPS = 5
PACKET_ID_MOTION_EX = 9
PACKET_ID_TYRE_SETS = 13
PACKET_ID_TIME_TRIAL = 14
PACKET_ID_LOBBY_INFO = 15

PACKET_LABELS = {
    PACKET_ID_MOTION: "motion",
    PACKET_ID_SESSION: "session",
    PACKET_ID_LAP_DATA: "lap_data",
    PACKET_ID_EVENT: "event",
    PACKET_ID_PARTICIPANTS: "participants",
    PACKET_ID_CAR_SETUPS: "car_setups",
    PACKET_ID_CAR_TELEMETRY: "car_telemetry",
    PACKET_ID_CAR_STATUS: "car_status",
    PACKET_ID_CAR_DAMAGE: "car_damage",
    PACKET_ID_MOTION_EX: "motion_ex",
    PACKET_ID_SESSION_HISTORY: "session_history",
    PACKET_ID_FINAL_CLASSIF: "final_classification",
    PACKET_ID_LAP_POSITIONS: "lap_positions",
    PACKET_ID_TYRE_SETS: "tyre_sets",
    PACKET_ID_TIME_TRIAL: "time_trial",
    PACKET_ID_LOBBY_INFO: "lobby_info",
}


@dataclass
class AgentReplaySummary:
    final_state: str
    participants: int
    events: int
    classification_entries: int
    live_entries: int
    telemetry_latest_entries: int
    telemetry_samples: int
    session_history_entries: int


@dataclass
class ReplaySummary:
    log_path: str
    parse_backend: str
    total_packets: int = 0
    packet_counts: dict[int, int] = field(default_factory=dict)
    parsed_packets: dict[int, int] = field(default_factory=dict)
    extractor_hits: dict[str, int] = field(default_factory=dict)
    sessions: list[int] = field(default_factory=list)
    parse_failures: list[str] = field(default_factory=list)
    agent: AgentReplaySummary | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _packet_label(packet_id: int) -> str:
    return PACKET_LABELS.get(packet_id, f"packet_{packet_id}")


def _packet_header(data: bytes) -> tuple[int, int, int]:
    header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    packet_format = int(header[0])
    packet_id = int(header[5])
    session_uid = int(header[6])
    return packet_id, session_uid, packet_format


def _iter_log_packets(log_path: Path):
    for data in replay_log(log_path):
        if len(data) < HEADER_SIZE:
            continue
        packet_id, session_uid, packet_format = _packet_header(data)
        yield data, packet_id, session_uid, packet_format


def analyze_raw_log(log_path: Path) -> ReplaySummary:
    packet_counts: Counter[int] = Counter()
    parsed_counts: Counter[int] = Counter()
    extractor_hits: Counter[str] = Counter()
    sessions: set[int] = set()
    parse_failures: list[str] = []

    for data, packet_id, session_uid, packet_format in _iter_log_packets(log_path):
        packet_counts[packet_id] += 1
        sessions.add(session_uid)

        parsed = parse_packet(packet_id, packet_format, data)
        if parsed is None:
            parse_failures.append(f"packet_id={packet_id} session_uid={session_uid}")
            continue

        parsed_counts[packet_id] += 1

        if packet_id == PACKET_ID_SESSION:
            info = extract_session_info(parsed)
            if info and info.get("track_id") is not None:
                extractor_hits["session_info"] += 1
        elif packet_id == PACKET_ID_PARTICIPANTS:
            if extract_participants(parsed):
                extractor_hits["participants"] += 1
        elif packet_id == PACKET_ID_EVENT:
            event = extract_event(parsed)
            if event and event.get("code"):
                extractor_hits["event"] += 1
        elif packet_id == PACKET_ID_MOTION:
            if extract_motion(parsed):
                extractor_hits["motion"] += 1
        elif packet_id == PACKET_ID_LAP_DATA:
            if extract_lap_data(parsed):
                extractor_hits["lap_data"] += 1
        elif packet_id == PACKET_ID_CAR_TELEMETRY:
            if extract_car_telemetry(parsed):
                extractor_hits["car_telemetry"] += 1
        elif packet_id == PACKET_ID_CAR_STATUS:
            if extract_car_status(parsed):
                extractor_hits["car_status"] += 1
        elif packet_id == PACKET_ID_CAR_DAMAGE:
            if extract_car_damage(parsed):
                extractor_hits["car_damage"] += 1
        elif packet_id == PACKET_ID_SESSION_HISTORY:
            if extract_session_history(parsed):
                extractor_hits["session_history"] += 1
        elif packet_id == PACKET_ID_LAP_POSITIONS:
            if extract_lap_positions(parsed):
                extractor_hits["lap_positions"] += 1
        elif packet_id == PACKET_ID_FINAL_CLASSIF:
            if extract_final_classification(parsed):
                extractor_hits["final_classification"] += 1

    return ReplaySummary(
        log_path=str(log_path),
        parse_backend=F1_PACKETS_API or "fallback",
        total_packets=sum(packet_counts.values()),
        packet_counts=dict(sorted(packet_counts.items())),
        parsed_packets=dict(sorted(parsed_counts.items())),
        extractor_hits=dict(sorted(extractor_hits.items())),
        sessions=sorted(sessions),
        parse_failures=parse_failures,
    )


def replay_log_into_agent(log_path: Path) -> AgentReplaySummary:
    detached_snapshot = None
    original_save_snapshot = telemetry_delivery.save_snapshot
    original_remove_snapshot = telemetry_delivery.remove

    def _capture_snapshot(session_uid: int, snapshot):
        nonlocal detached_snapshot
        detached_snapshot = snapshot.finalize()
        return {"session_uid": session_uid}

    agent = F1Agent()
    agent.ws.send_status = lambda *args, **kwargs: None
    agent.ws.send_live = lambda *args, **kwargs: None
    agent.raw_log.start_session = lambda *args, **kwargs: None
    agent.raw_log.write = lambda *args, **kwargs: None
    agent.raw_log.stop = lambda *args, **kwargs: None
    agent._send_status = lambda **extra: None
    agent._start_upload_worker = lambda session_uid, payload: None
    agent._scanner._active = False
    telemetry_delivery.save_snapshot = _capture_snapshot
    telemetry_delivery.remove = lambda session_uid: False

    try:
        for data, packet_id, session_uid, packet_format in _iter_log_packets(log_path):
            agent._on_packet(packet_id, session_uid, packet_format, data)
            if agent.sm.state.value == "race" and agent._telem._running:
                time.sleep(0.03)

        if agent._telem._running:
            time.sleep(0.35)
            agent._telem._running = False
            if agent._telem._thread:
                agent._telem._thread.join(timeout=1)
    finally:
        telemetry_delivery.save_snapshot = original_save_snapshot
        telemetry_delivery.remove = original_remove_snapshot

    telemetry_samples = sum(
        len(lap_entry.get("samples", []))
        for laps in agent._telem._buffers.values()
        for lap_entry in laps.values()
    )
    if detached_snapshot is not None:
        telemetry_samples += sum(
            len(lap_entry.get("samples", []))
            for laps in detached_snapshot.laps.values()
            for lap_entry in laps.values()
        )

    telemetry_latest_entries = max(len(agent._telem._latest), len(agent._live_data))
    if telemetry_latest_entries == 0 and detached_snapshot is not None:
        telemetry_latest_entries = len(detached_snapshot.laps)

    session_history_entries = len(agent._telem._session_history)
    if session_history_entries == 0 and detached_snapshot is not None:
        session_history_entries = len(detached_snapshot.session_history)

    return AgentReplaySummary(
        final_state=agent.sm.state.value,
        participants=len(agent._participants),
        events=len(agent._events),
        classification_entries=len(agent._final_classification),
        live_entries=len(agent._live_data),
        telemetry_latest_entries=telemetry_latest_entries,
        telemetry_samples=telemetry_samples,
        session_history_entries=session_history_entries,
    )


def run_replay(log_path: Path, include_agent: bool = False) -> ReplaySummary:
    summary = analyze_raw_log(log_path)
    if include_agent:
        summary.agent = replay_log_into_agent(log_path)
    return summary


def build_sample_packets(session_uid: int = 987654321) -> list[bytes]:
    packets: list[bytes] = []

    def apply_header(packet, packet_id: int, frame_identifier: int, session_time: float):
        packet.header.packet_format = 2025
        packet.header.game_year = 25
        packet.header.game_major_version = 1
        packet.header.game_minor_version = 0
        packet.header.packet_version = 1
        packet.header.packet_id = packet_id
        packet.header.session_uid = session_uid
        packet.header.session_time = session_time
        packet.header.frame_identifier = frame_identifier
        packet.header.overall_frame_identifier = frame_identifier
        packet.header.player_car_index = 0
        packet.header.secondary_player_car_index = 255
        return packet

    session_waiting = apply_header(f1_packets.PacketSessionData(), PACKET_ID_SESSION, 1, 1.0)
    session_waiting.weather = 2
    session_waiting.track_temperature = 31
    session_waiting.air_temperature = 22
    session_waiting.total_laps = 58
    session_waiting.session_type = 5
    session_waiting.track_id = 10
    packets.append(bytes(session_waiting))

    participants = apply_header(f1_packets.PacketParticipantsData(), PACKET_ID_PARTICIPANTS, 2, 1.2)
    participants.num_active_cars = 2
    participants.participants[0].name = b"LECLERC"
    participants.participants[0].ai_controlled = 0
    participants.participants[0].driver_id = 17
    participants.participants[0].team_id = 1
    participants.participants[0].race_number = 16
    participants.participants[0].nationality = 10
    participants.participants[0].platform = 1
    participants.participants[1].name = b"HAMILTON"
    participants.participants[1].ai_controlled = 0
    participants.participants[1].driver_id = 1
    participants.participants[1].team_id = 0
    participants.participants[1].race_number = 44
    participants.participants[1].nationality = 10
    participants.participants[1].platform = 1
    packets.append(bytes(participants))

    session_race = apply_header(f1_packets.PacketSessionData(), PACKET_ID_SESSION, 3, 2.0)
    session_race.weather = 2
    session_race.track_temperature = 31
    session_race.air_temperature = 22
    session_race.total_laps = 58
    session_race.session_type = 10
    session_race.track_id = 10
    packets.append(bytes(session_race))

    motion = apply_header(f1_packets.PacketMotionData(), PACKET_ID_MOTION, 4, 2.1)
    motion.car_motion_data[0].world_position_x = 123.4
    motion.car_motion_data[0].world_position_z = 456.7
    motion.car_motion_data[1].world_position_x = 124.0
    motion.car_motion_data[1].world_position_z = 457.2
    packets.append(bytes(motion))

    telemetry = apply_header(f1_packets.PacketCarTelemetryData(), PACKET_ID_CAR_TELEMETRY, 5, 2.15)
    telemetry.car_telemetry_data[0].speed = 312
    telemetry.car_telemetry_data[0].throttle = 0.95
    telemetry.car_telemetry_data[0].gear = 8
    telemetry.car_telemetry_data[0].drs = 1
    telemetry.car_telemetry_data[0].steer = 0.12
    telemetry.car_telemetry_data[1].speed = 308
    telemetry.car_telemetry_data[1].throttle = 0.91
    telemetry.car_telemetry_data[1].gear = 8
    telemetry.car_telemetry_data[1].drs = 1
    telemetry.car_telemetry_data[1].steer = -0.08
    packets.append(bytes(telemetry))

    status = apply_header(f1_packets.PacketCarStatusData(), PACKET_ID_CAR_STATUS, 6, 2.2)
    status.car_status_data[0].visual_tyre_compound = 18
    status.car_status_data[0].ers_store_energy = 2_500_000
    status.car_status_data[0].ers_deployed_this_lap = 123_456
    status.car_status_data[0].fuel_in_tank = 21.5
    status.car_status_data[0].fuel_remaining_laps = 11.4
    status.car_status_data[0].drs_allowed = 1
    status.car_status_data[1].visual_tyre_compound = 17
    status.car_status_data[1].ers_store_energy = 2_000_000
    status.car_status_data[1].ers_deployed_this_lap = 111_111
    status.car_status_data[1].fuel_in_tank = 20.2
    status.car_status_data[1].fuel_remaining_laps = 10.9
    status.car_status_data[1].drs_allowed = 1
    packets.append(bytes(status))

    damage = apply_header(f1_packets.PacketCarDamageData(), PACKET_ID_CAR_DAMAGE, 7, 2.25)
    for index, wear in enumerate([10.5, 11.5, 12.5, 13.5]):
        damage.car_damage_data[0].tyres_wear[index] = wear
        damage.car_damage_data[0].tyres_damage[index] = index + 1
    damage.car_damage_data[0].front_left_wing_damage = 4
    damage.car_damage_data[0].front_right_wing_damage = 5
    damage.car_damage_data[0].rear_wing_damage = 6
    packets.append(bytes(damage))

    lap = apply_header(f1_packets.PacketLapData(), PACKET_ID_LAP_DATA, 8, 2.3)
    lap.lap_data[0].current_lap_num = 3
    lap.lap_data[0].lap_distance = 222.2
    lap.lap_data[0].current_lap_time_in_ms = 54_321
    lap.lap_data[0].last_lap_time_in_ms = 91_234
    lap.lap_data[0].car_position = 1
    lap.lap_data[0].num_pit_stops = 1
    lap.lap_data[1].current_lap_num = 3
    lap.lap_data[1].lap_distance = 219.7
    lap.lap_data[1].current_lap_time_in_ms = 54_850
    lap.lap_data[1].last_lap_time_in_ms = 91_900
    lap.lap_data[1].car_position = 2
    lap.lap_data[1].num_pit_stops = 1
    packets.append(bytes(lap))

    history = apply_header(f1_packets.PacketSessionHistoryData(), PACKET_ID_SESSION_HISTORY, 9, 2.35)
    history.car_idx = 0
    history.num_laps = 1
    history.best_lap_time_lap_num = 1
    history.best_sector1_lap_num = 1
    history.best_sector2_lap_num = 1
    history.best_sector3_lap_num = 1
    history.lap_history_data[0].lap_time_in_ms = 91_234
    history.lap_history_data[0].sector1_time_ms_part = 30_000
    history.lap_history_data[0].sector2_time_ms_part = 31_000
    history.lap_history_data[0].sector3_time_ms_part = 30_234
    history.lap_history_data[0].lap_valid_bit_flags = 1
    packets.append(bytes(history))

    positions = apply_header(f1_packets.PacketLapPositionsData(), PACKET_ID_LAP_POSITIONS, 10, 2.4)
    positions.num_laps = 1
    positions.lap_start = 3
    positions.position_for_vehicle_idx[0] = 1
    positions.position_for_vehicle_idx[1] = 2
    packets.append(bytes(positions))

    event = apply_header(f1_packets.PacketEventData(), PACKET_ID_EVENT, 11, 2.45)
    event.event_string_code = (ctypes.c_uint8 * 4)(*b"FTLP")
    event.event_details.fastest_lap.vehicle_idx = 0
    event.event_details.fastest_lap.lap_time = 92.345
    packets.append(bytes(event))

    final = apply_header(f1_packets.PacketFinalClassificationData(), PACKET_ID_FINAL_CLASSIF, 12, 3.0)
    final.num_cars = 2
    final.classification_data[0].position = 1
    final.classification_data[0].num_laps = 58
    final.classification_data[0].grid_position = 2
    final.classification_data[0].num_pit_stops = 1
    final.classification_data[0].result_status = 3
    final.classification_data[0].best_lap_time_in_ms = 88_111
    final.classification_data[0].total_race_time = 5_432.1
    final.classification_data[0].penalties_time = 5
    final.classification_data[0].num_penalties = 1
    final.classification_data[0].num_tyre_stints = 2
    final.classification_data[0].tyre_stints_actual[0] = 18
    final.classification_data[0].tyre_stints_actual[1] = 17
    final.classification_data[0].tyre_stints_end_laps[0] = 20
    final.classification_data[0].tyre_stints_end_laps[1] = 58
    final.classification_data[1].position = 2
    final.classification_data[1].num_laps = 58
    final.classification_data[1].grid_position = 1
    final.classification_data[1].num_pit_stops = 1
    final.classification_data[1].result_status = 3
    final.classification_data[1].best_lap_time_in_ms = 88_900
    final.classification_data[1].total_race_time = 5_439.4
    final.classification_data[1].num_tyre_stints = 2
    final.classification_data[1].tyre_stints_actual[0] = 17
    final.classification_data[1].tyre_stints_actual[1] = 18
    final.classification_data[1].tyre_stints_end_laps[0] = 24
    final.classification_data[1].tyre_stints_end_laps[1] = 58
    packets.append(bytes(final))

    return packets


def write_sample_raw_log(log_path: Path, session_uid: int = 987654321) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "wb") as handle:
        for packet in build_sample_packets(session_uid=session_uid):
            handle.write(struct.pack("<I", len(packet)))
            handle.write(packet)
    return log_path


def run_self_test() -> ReplaySummary:
    with tempfile.TemporaryDirectory(prefix="f1t_replay_") as tmp_dir:
        log_path = write_sample_raw_log(Path(tmp_dir) / "fixture_session_track10.bin")
        return run_replay(log_path, include_agent=True)


def _print_summary(summary: ReplaySummary) -> None:
    print(f"log: {summary.log_path}")
    print(f"parse_backend: {summary.parse_backend}")
    print(f"total_packets: {summary.total_packets}")
    print(f"packet_counts: {summary.packet_counts}")
    print(f"parsed_packets: {summary.parsed_packets}")
    print(f"extractor_hits: {summary.extractor_hits}")
    print(f"sessions: {summary.sessions}")
    if summary.parse_failures:
        print(f"parse_failures: {summary.parse_failures}")
    if summary.agent:
        print(f"agent: {summary.agent}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay RawLogger binary logs through the packet parser and agent.")
    parser.add_argument("--log", type=Path, help="Path to a RawLogger-format binary log.")
    parser.add_argument("--write-fixture", type=Path, help="Write a synthetic RawLogger fixture log to this path.")
    parser.add_argument("--agent", action="store_true", help="Also replay the log through F1Agent.")
    parser.add_argument("--self-test", action="store_true", help="Generate a temporary fixture log and replay it.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a text summary.")
    args = parser.parse_args()

    if not args.log and not args.write_fixture and not args.self_test:
        parser.error("Specify --log, --write-fixture, or --self-test.")

    if args.write_fixture:
        fixture_path = write_sample_raw_log(args.write_fixture)
        if not args.log and not args.self_test:
            print(fixture_path)
            return 0

    if args.self_test:
        summary = run_self_test()
    else:
        if args.log is None:
            parser.error("--log is required unless --self-test is used.")
        summary = run_replay(args.log, include_agent=args.agent)

    if args.json:
        print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
