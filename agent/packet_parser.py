"""
Парсит сырые байты UDP пакетов F1 25 через библиотеку f1-packets.
Возвращает нормализованные Python dict для каждого типа пакета.
"""
from __future__ import annotations

import ctypes

from shared.packet_format import get_adapter


try:
    import f1.packets as _f1_packets
except ImportError:
    _f1_packets = None


_PACKET_RESOLVER = None
F1_PACKETS_API = None

_MANUAL_PACKET_CLASS_NAMES_2025 = {
    0: "PacketMotionData",
    1: "PacketSessionData",
    2: "PacketLapData",
    3: "PacketEventData",
    4: "PacketParticipantsData",
    5: "PacketCarSetupData",
    6: "PacketCarTelemetryData",
    7: "PacketCarStatusData",
    8: "PacketCarDamageData",
    9: "PacketMotionExData",
    10: "PacketSessionHistoryData",
    11: "PacketFinalClassificationData",
    12: "PacketLapPositionsData",
    13: "PacketTyreSetsData",
    14: "PacketTimeTrialData",
    15: "PacketLobbyInfoData",
}

_EVENT_DETAIL_FIELD_BY_CODE = {
    "FTLP": "m_fastestLap",
    "RTMT": "m_retirement",
    "DRSD": "m_drsDisabled",
    "TMPT": "m_teamMateInPits",
    "RCWN": "m_raceWinner",
    "PENA": "m_penalty",
    "SPTP": "m_speedTrap",
    "STLG": "m_startLights",
    "DTSV": "m_driveThroughPenaltyServed",
    "SGSV": "m_stopGoPenaltyServed",
    "FLBK": "m_flashback",
    "BUTN": "m_buttons",
    "OVTK": "m_overtake",
    "SCAR": "m_safetyCar",
    "C1SL": "m_collision",
}

_CAMEL_TOKEN_MAP = {
    "id": "Id",
    "idx": "Idx",
    "uid": "UID",
    "ms": "MS",
    "mguk": "MGUK",
    "mguh": "MGUH",
    "rpm": "RPM",
    "x": "X",
    "y": "Y",
    "z": "Z",
    "pb": "PB",
}


def _uses_incompatible_2025_map() -> bool:
    if _f1_packets is None or not hasattr(_f1_packets, "HEADER_FIELD_TO_PACKET_TYPE"):
        return False

    expected = {
        packet_id: class_name
        for packet_id, class_name in _MANUAL_PACKET_CLASS_NAMES_2025.items()
    }
    mapping = _f1_packets.HEADER_FIELD_TO_PACKET_TYPE

    for packet_id, class_name in expected.items():
        packet_type = mapping.get((2025, 1, packet_id))
        if packet_type is None or packet_type.__name__ != class_name:
            return True
    return False


_MANUAL_2025_MAP_REQUIRED = _uses_incompatible_2025_map()

if _f1_packets is not None:
    if hasattr(_f1_packets, "unpack_udp_packet"):
        _PACKET_RESOLVER = _f1_packets.unpack_udp_packet
        F1_PACKETS_API = "unpack_udp_packet"
    elif hasattr(_f1_packets, "resolve"):
        _PACKET_RESOLVER = _f1_packets.resolve
        F1_PACKETS_API = "resolve+manual_2025_packet_map" if _MANUAL_2025_MAP_REQUIRED else "resolve"

F1_PACKETS_AVAILABLE = _PACKET_RESOLVER is not None

if not F1_PACKETS_AVAILABLE:
    print("[PARSER] WARNING: compatible f1-packets parser API not found. Install/update f1-packets.")


def parse_packet(packet_id: int, packet_format: int, data: bytes) -> dict | None:
    """
    Парсит пакет и возвращает dict с полями.
    Возвращает None если пакет неизвестен или ошибка.
    """
    if not F1_PACKETS_AVAILABLE:
        return _fallback_parse(packet_id, data)

    try:
        pkt = _resolve_packet(packet_id, packet_format, data)
        if pkt is None:
            return None

        adapter = get_adapter(packet_format)
        raw = _normalize_packet_tree(_to_dict(pkt))
        return adapter.normalize(packet_id, raw)
    except Exception as e:
        print(f"[PARSER] Parse error packet_id={packet_id}: {e}")
        return None


def _resolve_packet(packet_id: int, packet_format: int, data: bytes):
    if _f1_packets is None or _PACKET_RESOLVER is None:
        return None

    if packet_format == 2025 and _MANUAL_2025_MAP_REQUIRED:
        packet_class_name = _MANUAL_PACKET_CLASS_NAMES_2025.get(packet_id)
        packet_cls = getattr(_f1_packets, packet_class_name, None) if packet_class_name else None
        if packet_cls is not None and hasattr(packet_cls, "unpack"):
            return packet_cls.unpack(data)

    return _PACKET_RESOLVER(data)


def _to_dict(obj):
    """Рекурсивно конвертирует ctypes структуру в dict."""
    if isinstance(obj, dict):
        return {key: _to_dict(value) for key, value in obj.items()}
    if isinstance(obj, ctypes.Array):
        if obj._type_ is ctypes.c_char:
            return bytes(obj).split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        return [_to_dict(item) for item in obj]
    if hasattr(obj, "_fields_"):
        return {name: _to_dict(getattr(obj, name)) for name, _ in obj._fields_}
    if isinstance(obj, (bytes, bytearray)):
        return bytes(obj)
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        return [_to_dict(item) for item in obj]
    return obj


def _normalize_packet_tree(obj):
    if isinstance(obj, dict):
        normalized = {}
        for key, value in obj.items():
            normalized_key = "_header" if key == "header" else _normalize_packet_key(key)
            normalized[normalized_key] = _normalize_packet_tree(value)
        return normalized
    if isinstance(obj, list):
        return [_normalize_packet_tree(item) for item in obj]
    return obj


def _normalize_packet_key(key: str) -> str:
    if key.startswith("m_") or key.startswith("_"):
        return key

    parts = key.split("_")
    if not parts:
        return key

    tail = []
    for token in parts[1:]:
        if token in _CAMEL_TOKEN_MAP:
            tail.append(_CAMEL_TOKEN_MAP[token])
        else:
            tail.append(token.capitalize())
    return "m_" + parts[0] + "".join(tail)


def _fallback_parse(packet_id: int, data: bytes) -> dict | None:
    """Минимальный fallback без f1-packets — только для Session и Event."""
    # Пока возвращаем пустой dict с признаком raw
    return {"_raw": True, "_packet_id": packet_id, "_size": len(data)}


def _lower_camelize_dict_keys(obj):
    if isinstance(obj, dict):
        normalized = {}
        for key, value in obj.items():
            clean_key = key[2:] if key.startswith("m_") else key
            if clean_key.startswith("_"):
                clean_key = clean_key[1:]
            if clean_key:
                clean_key = clean_key[0].lower() + clean_key[1:]
            normalized[clean_key] = _lower_camelize_dict_keys(value)
        return normalized
    if isinstance(obj, list):
        return [_lower_camelize_dict_keys(item) for item in obj]
    return obj


def _time_ms_from_parts(raw: dict, base_key: str) -> int:
    direct = raw.get(f"{base_key}InMS")
    if direct is not None:
        return int(direct)

    part_ms = raw.get(f"{base_key}MSPart")
    if part_ms is None:
        return 0

    part_minutes = raw.get(f"{base_key}MinutesPart", 0) or 0
    return int(part_minutes) * 60_000 + int(part_ms)


# ---------------------------------------------------------------------------
# Хелперы для извлечения конкретных данных
# ---------------------------------------------------------------------------

def extract_session_info(parsed: dict) -> dict | None:
    """Из Session пакета (ID:1) извлекает track_id, session_type, weather, temps."""
    if not parsed:
        return None
    try:
        return {
            "track_id":     parsed.get("m_trackId"),
            "session_type": parsed.get("m_sessionType"),
            "weather":      parsed.get("m_weather"),
            "air_temp":     parsed.get("m_airTemperature"),
            "track_temp":   parsed.get("m_trackTemperature"),
            "total_laps":   parsed.get("m_totalLaps"),
            "packet_format": parsed.get("_header", {}).get("m_packetFormat"),
        }
    except Exception:
        return None


def extract_participants(parsed: dict) -> list[dict]:
    """Из Participants пакета (ID:4) извлекает список участников."""
    if not parsed:
        return []
    try:
        num = parsed.get("m_numActiveCars", 0)
        participants_raw = parsed.get("m_participants", [])
        result = []
        for i, p in enumerate(participants_raw[:num]):
            result.append({
                "vehicle_index":  i,
                "m_aiControlled": p.get("m_aiControlled", 1),
                "m_driverId":     p.get("m_driverId", 255),
                "m_teamId":       p.get("m_teamId", 255),
                "m_raceNumber":   p.get("m_raceNumber", 0),
                "m_name":         _decode_name(p.get("m_name", "")),
                "m_nationality":  p.get("m_nationality", 0),
                "m_platform":     p.get("m_platform", 0),
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_participants error: {e}")
        return []


def extract_final_classification(parsed: dict) -> list[dict]:
    """Из FinalClassification пакета (ID:11) извлекает результаты всех машин."""
    if not parsed:
        return []
    try:
        num = parsed.get("m_numCars", 0)
        cars = parsed.get("m_classificationData", [])
        result = []
        for i, c in enumerate(cars[:num]):
            stints_raw = c.get("m_tyreStintsActual", [])
            stints_visual = c.get("m_tyreStintsVisual", [])
            stints_end_laps = c.get("m_tyreStintsEndLaps", [])

            stints = []
            for j, compound in enumerate(stints_raw):
                end_lap = stints_end_laps[j] if j < len(stints_end_laps) else 0
                if end_lap == 0 and j > 0:
                    break
                stints.append({"compound": compound, "end_lap": end_lap})

            result.append({
                "vehicle_index":   i,
                "m_position":      c.get("m_position", 0),
                "m_numLaps":       c.get("m_numLaps", 0),
                "m_gridPosition":  c.get("m_gridPosition", 0),
                "m_numPitStops":   c.get("m_numPitStops", 0),
                "m_resultStatus":  c.get("m_resultStatus", 0),
                "m_bestLapTimeInMS": c.get("m_bestLapTimeInMS", 0),
                "m_totalRaceTime": c.get("m_totalRaceTime", 0.0),
                "m_penaltiesTime": c.get("m_penaltiesTime", 0),
                "m_numPenalties":  c.get("m_numPenalties", 0),
                "m_numTyreStints": c.get("m_numTyreStints", 1),
                "tyre_stints":     stints,
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_final_classification error: {e}")
        return []


def extract_event(parsed: dict) -> dict | None:
    """Из Event пакета (ID:3) извлекает код события и данные."""
    if not parsed:
        return None
    try:
        code_bytes = parsed.get("m_eventStringCode", "")
        if isinstance(code_bytes, (list, bytes)):
            code = bytes(code_bytes).decode("ascii", errors="ignore").rstrip("\x00")
        else:
            code = str(code_bytes)

        event_data = parsed.get("m_eventDetails", {})
        detail_key = _EVENT_DETAIL_FIELD_BY_CODE.get(code[:4])
        if isinstance(event_data, dict) and detail_key:
            event_data = event_data.get(detail_key, {})
        elif not isinstance(event_data, dict):
            event_data = _to_dict(event_data) if hasattr(event_data, "_fields_") else {}

        return {"code": code[:4], "data": _lower_camelize_dict_keys(event_data or {})}
    except Exception as e:
        print(f"[PARSER] extract_event error: {e}")
        return None


def extract_car_telemetry(parsed: dict, num_cars: int = 20) -> list[dict]:
    """
    Из CarTelemetry пакета (ID:6) — speed, throttle, brake, gear, drs, steer.
    Возвращает список по vehicle_index.
    """
    if not parsed:
        return []
    try:
        cars = parsed.get("m_carTelemetryData", [])
        result = []
        for i, c in enumerate(cars[:num_cars]):
            result.append({
                "vehicle_index": i,
                "speed":    c.get("m_speed", 0),          # км/ч
                "throttle": c.get("m_throttle", 0.0),     # 0.0–1.0
                "brake":    c.get("m_brake", 0.0),        # 0.0–1.0
                "gear":     c.get("m_gear", 0),           # 0–8
                "drs":      c.get("m_drs", 0),            # 0/1
                "steer":    c.get("m_steer", 0.0),        # -1.0–1.0
                "tyres_surface_temp": c.get("m_tyresSurfaceTemperature", [0, 0, 0, 0]),
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_car_telemetry error: {e}")
        return []


def extract_motion(parsed: dict, num_cars: int = 20) -> list[dict]:
    """
    Из Motion пакета (ID:0) — world_x, world_z (координаты на треке).
    """
    if not parsed:
        return []
    try:
        cars = parsed.get("m_carMotionData", [])
        result = []
        for i, c in enumerate(cars[:num_cars]):
            result.append({
                "vehicle_index": i,
                "world_x": c.get("m_worldPositionX", 0.0),
                "world_z": c.get("m_worldPositionZ", 0.0),
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_motion error: {e}")
        return []


def extract_lap_data(parsed: dict, num_cars: int = 20) -> list[dict]:
    """
    Из LapData пакета (ID:2) — lap_number, lap_distance, current_lap_time_ms.
    """
    if not parsed:
        return []
    try:
        cars = parsed.get("m_lapData", [])
        header = parsed.get("_header", {})
        session_time = header.get("m_sessionTime", 0.0)
        result = []
        for i, c in enumerate(cars[:num_cars]):
            result.append({
                "vehicle_index":     i,
                "lap_number":        c.get("m_currentLapNum", 0),
                "lap_distance":      c.get("m_lapDistance", 0.0),
                "current_lap_ms":    c.get("m_currentLapTimeInMS", 0),
                "last_lap_ms":       c.get("m_lastLapTimeInMS", 0),
                "best_lap_ms":       c.get("m_bestLapTimeInMS", 0),
                "car_position":      c.get("m_carPosition", 0),
                "num_pit_stops":     c.get("m_numPitStops", 0),
                "session_time":      session_time,
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_lap_data error: {e}")
        return []


def extract_car_status(parsed: dict, num_cars: int = 20) -> list[dict]:
    """
    Из CarStatus пакета (ID:7) — ERS deployed/stored, fuel, tyre wear.
    """
    if not parsed:
        return []
    try:
        cars = parsed.get("m_carStatusData", [])
        result = []
        for i, c in enumerate(cars[:num_cars]):
            # Visual tyre compound mapping
            visual = c.get("m_visualTyreCompound", 0)
            compound_map = {16: "H", 17: "M", 18: "S", 7: "I", 8: "W"}
            tyre_str = compound_map.get(visual, "?")

            result.append({
                "vehicle_index":    i,
                "ers_deploy":       round(c.get("m_ersDeployedThisLap", 0.0), 2),
                "ers_store":        round(c.get("m_ersStoreEnergy", 0.0), 2),
                "ers_mode":         c.get("m_ersDeployMode", 0),
                "fuel_in_tank":     round(c.get("m_fuelInTank", 0.0), 2),
                "fuel_remaining_laps": round(c.get("m_fuelRemainingLaps", 0.0), 1),
                "visual_tyre":      tyre_str,
                "drs_allowed":      c.get("m_drsAllowed", 0),
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_car_status error: {e}")
        return []


def extract_car_damage(parsed: dict, num_cars: int = 20) -> list[dict]:
    """
    Из CarDamage пакета (ID:8) — износ шин и повреждения.
    """
    if not parsed:
        return []
    try:
        cars = parsed.get("m_carDamageData", [])
        result = []
        for i, c in enumerate(cars[:num_cars]):
            tyres_wear = c.get("m_tyresWear", [0, 0, 0, 0])
            tyres_damage = c.get("m_tyresDamage", [0, 0, 0, 0])
            result.append({
                "vehicle_index": i,
                "tyres_wear":    [round(w, 1) for w in tyres_wear[:4]],   # [RL, RR, FL, FR] %
                "tyres_damage":  [round(d, 1) for d in tyres_damage[:4]],
                "front_left_wing_damage":  round(c.get("m_frontLeftWingDamage", 0), 1),
                "front_right_wing_damage": round(c.get("m_frontRightWingDamage", 0), 1),
                "rear_wing_damage":        round(c.get("m_rearWingDamage", 0), 1),
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_car_damage error: {e}")
        return []


def extract_session_history(parsed: dict) -> dict | None:
    """
    Из SessionHistory пакета (ID:10) — история кругов одного пилота.
    Содержит времена кругов и секторов.
    Пакет приходит per-vehicle (m_carIdx указывает на какую машину).
    """
    if not parsed:
        return None
    try:
        car_idx = parsed.get("m_carIdx", 0)
        num_laps = parsed.get("m_numLaps", 0)
        best_lap_num = parsed.get("m_bestLapTimeLapNum", 0)
        best_s1_lap = parsed.get("m_bestSector1LapNum", 0)
        best_s2_lap = parsed.get("m_bestSector2LapNum", 0)
        best_s3_lap = parsed.get("m_bestSector3LapNum", 0)

        laps_raw = parsed.get("m_lapHistoryData", [])
        laps = []
        for i, lap in enumerate(laps_raw[:num_laps]):
            laps.append({
                "lap_number":   i + 1,
                "lap_time_ms":  lap.get("m_lapTimeInMS", 0),
                "sector1_ms":   _time_ms_from_parts(lap, "m_sector1Time"),
                "sector2_ms":   _time_ms_from_parts(lap, "m_sector2Time"),
                "sector3_ms":   _time_ms_from_parts(lap, "m_sector3Time"),
                "lap_valid":    lap.get("m_lapValidBitFlags", 0) & 0x01 == 0x01,
            })

        return {
            "vehicle_index": car_idx,
            "num_laps":      num_laps,
            "best_lap_num":  best_lap_num,
            "best_s1_lap":   best_s1_lap,
            "best_s2_lap":   best_s2_lap,
            "best_s3_lap":   best_s3_lap,
            "laps":          laps,
        }
    except Exception as e:
        print(f"[PARSER] extract_session_history error: {e}")
        return None


def extract_lap_positions(parsed: dict, num_cars: int = 20) -> list[dict]:
    """
    Из LapPositions пакета (ID:12) — позиции машин.
    Новый пакет в F1 25.
    """
    if not parsed:
        return []
    try:
        # The packet may have different field names depending on f1-packets version
        # Try common structures
        positions_data = parsed.get("m_lapPositions", parsed.get("m_lapPositionData", []))
        if positions_data:
            result = []
            for i, p in enumerate(positions_data[:num_cars]):
                if isinstance(p, dict):
                    result.append({
                        "vehicle_index": i,
                        "position": p.get("m_position", p.get("m_carPosition", i + 1)),
                        "lap_number": p.get("m_lapNumber", p.get("m_currentLapNum", 0)),
                    })
                elif isinstance(p, (int, float)):
                    result.append({
                        "vehicle_index": i,
                        "position": int(p),
                        "lap_number": 0,
                    })
            return result

        flat_positions = parsed.get("m_positionForVehicleIdx", [])
        lap_count = int(parsed.get("m_numLaps", 0) or 0)
        lap_start = int(parsed.get("m_lapStart", 0) or 0)
        if not flat_positions or lap_count <= 0:
            return []

        result = []
        cars_per_lap = 22
        latest_lap_index = max(lap_count - 1, 0)
        latest_lap_number = lap_start + latest_lap_index
        start = latest_lap_index * cars_per_lap

        for i, position in enumerate(flat_positions[start:start + num_cars]):
            if int(position) <= 0:
                continue
            result.append({
                "vehicle_index": i,
                "position": int(position),
                "lap_number": latest_lap_number,
            })
        return result
    except Exception as e:
        print(f"[PARSER] extract_lap_positions error: {e}")
        return []


def _decode_name(raw) -> str:
    if isinstance(raw, (list, bytes)):
        try:
            return bytes(raw).decode("utf-8", errors="ignore").rstrip("\x00")
        except Exception:
            return ""
    return str(raw).rstrip("\x00")
