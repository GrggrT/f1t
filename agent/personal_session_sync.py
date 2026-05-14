"""
Persist personal-mode session history for the launcher profile.

These writes use the authenticated launcher user's bearer token and are kept
separate from the agent-token race upload pipeline.
"""
from __future__ import annotations

from typing import Callable

import httpx

import agent.config as agent_config
from agent.telemetry_buffer import TelemetrySnapshot
from shared.f1_mappings import get_session_type_name, get_track_name


Observer = Callable[[str, dict], None]


def _emit(observer: Observer | None, event: str, **payload) -> None:
    if not observer:
        return
    try:
        observer(event, payload)
    except Exception:
        pass


def _auth_headers() -> dict[str, str]:
    token = (agent_config.AUTH_TOKEN or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _extract_http_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    detail = None
    if isinstance(payload, dict):
        detail = payload.get("message") or payload.get("detail") or payload.get("error")

    if detail:
        return f"HTTP {response.status_code}: {detail}"
    return f"HTTP {response.status_code}"


def _select_vehicle_index(
    snapshot: TelemetrySnapshot,
    participants: list[dict] | None = None,
    classification: list[dict] | None = None,
) -> int | None:
    if 0 in snapshot.session_history or 0 in snapshot.laps:
        return 0

    participants = participants or []
    for participant in participants:
        if participant.get("m_aiControlled") != 0:
            continue
        vehicle_index = int(participant.get("vehicle_index", -1) or -1)
        if vehicle_index in snapshot.session_history or vehicle_index in snapshot.laps:
            return vehicle_index

    classification = classification or []
    for row in classification:
        vehicle_index = int(row.get("vehicle_index", -1) or -1)
        if vehicle_index in snapshot.session_history or vehicle_index in snapshot.laps:
            return vehicle_index

    candidates = sorted(set(snapshot.session_history) | set(snapshot.laps))
    return candidates[0] if candidates else None


def _build_laps(snapshot: TelemetrySnapshot, vehicle_index: int) -> list[dict]:
    merged: dict[int, dict] = {}

    history = snapshot.session_history.get(vehicle_index) or {}
    for lap in history.get("laps", []):
        if not isinstance(lap, dict):
            continue
        lap_number = int(lap.get("lap_number", 0) or 0)
        if lap_number <= 0:
            continue
        lap_time_ms = lap.get("lap_time_ms")
        if not lap_time_ms:
            lap_time_ms = (snapshot.laps.get(vehicle_index) or {}).get(lap_number, {}).get("lap_time_ms")
        if not lap_time_ms:
            continue
        merged[lap_number] = {
            "lap_number": lap_number,
            "lap_time_ms": int(lap_time_ms),
            "sector1_ms": int(lap.get("sector1_ms", 0) or 0) or None,
            "sector2_ms": int(lap.get("sector2_ms", 0) or 0) or None,
            "sector3_ms": int(lap.get("sector3_ms", 0) or 0) or None,
            "tyre_compound": None,
            "valid": bool(lap.get("lap_valid", True)),
        }

    for lap_number, lap_entry in sorted((snapshot.laps.get(vehicle_index) or {}).items()):
        number = int(lap_number or 0)
        if number <= 0:
            continue
        lap_time_ms = lap_entry.get("lap_time_ms")
        if not lap_time_ms:
            continue
        merged.setdefault(
            number,
            {
                "lap_number": number,
                "lap_time_ms": int(lap_time_ms),
                "sector1_ms": None,
                "sector2_ms": None,
                "sector3_ms": None,
                "tyre_compound": None,
                "valid": True,
            },
        )

    return [merged[number] for number in sorted(merged)]


def sync_personal_session(
    session_uid: int,
    snapshot: TelemetrySnapshot,
    *,
    track_id: int | None,
    session_type: int | None,
    participants: list[dict] | None = None,
    classification: list[dict] | None = None,
    observer: Observer | None = None,
) -> bool:
    headers = _auth_headers()
    if not headers:
        _emit(observer, "skipped", session_uid=session_uid, reason="missing_auth_token")
        return False

    vehicle_index = _select_vehicle_index(
        snapshot,
        participants=participants,
        classification=classification,
    )
    if vehicle_index is None:
        _emit(observer, "skipped", session_uid=session_uid, reason="missing_vehicle_index")
        return False

    laps = _build_laps(snapshot.finalize(), vehicle_index)
    if not laps:
        _emit(observer, "skipped", session_uid=session_uid, reason="no_laps")
        return False

    track_value = int(track_id or -1)
    track_name = get_track_name(track_value) if track_value >= 0 else "Unknown Track"
    session_label = get_session_type_name(int(session_type or 0))

    _emit(
        observer,
        "attempt",
        session_uid=session_uid,
        track_id=track_id,
        track_name=track_name,
        session_type=session_label,
        laps=len(laps),
    )

    try:
        with httpx.Client(timeout=20) as client:
            created = client.post(
                f"{agent_config.SERVER_URL}/api/practice/sessions",
                json={
                    "track_id": max(track_value, 0),
                    "track_name": track_name,
                    "session_type": session_label,
                },
                headers=headers,
            )
            if created.status_code != 200:
                raise RuntimeError(_extract_http_error(created))

            session_id = created.json().get("id")
            if not session_id:
                raise RuntimeError("Practice session id was not returned by backend.")

            added = client.post(
                f"{agent_config.SERVER_URL}/api/practice/sessions/{session_id}/laps",
                json={"laps": laps},
                headers=headers,
            )
            if added.status_code != 200:
                raise RuntimeError(_extract_http_error(added))

            ended = client.post(
                f"{agent_config.SERVER_URL}/api/practice/sessions/{session_id}/end",
                headers=headers,
            )
            if ended.status_code != 200:
                raise RuntimeError(_extract_http_error(ended))

        _emit(
            observer,
            "succeeded",
            session_uid=session_uid,
            session_id=session_id,
            track_id=track_id,
            track_name=track_name,
            session_type=session_label,
            laps=len(laps),
        )
        return True

    except Exception as exc:
        _emit(
            observer,
            "failed",
            session_uid=session_uid,
            track_id=track_id,
            track_name=track_name,
            session_type=session_label,
            error=str(exc) or exc.__class__.__name__,
        )
        return False
