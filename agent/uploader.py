"""
Uploads race results to the backend with retry and local caching.
Observer hooks expose upload attempts and failures to the launcher.
"""
from __future__ import annotations

import time
from typing import Callable

import httpx

from agent import config, local_cache, telemetry_delivery
from agent.config import AuthFailureError, RETRY_DELAYS, SEASON_ID, SERVER_URL
from shared.f1_mappings import get_track_name, get_tyre_name


Observer = Callable[[str, dict], None]


def _emit(observer: Observer | None, event: str, **payload) -> None:
    if not observer:
        return
    try:
        observer(event, payload)
    except Exception:
        pass


def build_race_payload(
    session_uid: int,
    packet_format: int,
    track_id: int,
    session_info: dict,
    participants: list[dict],
    classification: list[dict],
    events: list[dict],
    fastest_lap_vehicle_idx: int | None = None,
) -> dict:
    """
    Build the payload for POST /api/race/submit from parsed UDP data.
    """
    participants_map = {p["vehicle_index"]: p for p in participants}

    result_participants = []
    for clf in classification:
        vidx = clf["vehicle_index"]
        part = participants_map.get(vidx, {})

        is_human = part.get("m_aiControlled", 1) == 0
        driver_id = part.get("m_driverId", 255)
        team_id = part.get("m_teamId", 255)
        steam_name = part.get("m_name", "") if is_human else None

        tyre_stints = []
        for stint in clf.get("tyre_stints", []):
            tyre_stints.append({
                "compound": get_tyre_name(stint.get("compound", 0)),
                "laps": stint.get("end_lap", 0),
            })

        result_participants.append({
            "vehicle_index": vidx,
            "is_human": is_human,
            "steam_name": steam_name,
            "driver_id": driver_id,
            "team_id": team_id,
            "grid_position": clf.get("m_gridPosition"),
            "position": clf.get("m_position"),
            "result_status": clf.get("m_resultStatus", 3),
            "total_race_time": clf.get("m_totalRaceTime"),
            "best_lap_ms": clf.get("m_bestLapTimeInMS"),
            "penalties_time": clf.get("m_penaltiesTime"),
            "num_penalties": clf.get("m_numPenalties"),
            "num_pit_stops": clf.get("m_numPitStops"),
            "tyre_stints": tyre_stints,
            "has_fastest_lap": fastest_lap_vehicle_idx == vidx,
        })

    return {
        "season_id": SEASON_ID,
        "session_uid": session_uid,
        "packet_format": packet_format,
        "track_id": track_id,
        "weather_start": session_info.get("weather_start"),
        "weather_end": session_info.get("weather_end"),
        "total_laps": session_info.get("total_laps"),
        "air_temp": session_info.get("air_temp"),
        "track_temp": session_info.get("track_temp"),
        "participants": result_participants,
        "events": events,
    }


def _pending_uploads_count() -> int:
    return local_cache.pending_count()


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


def _agent_headers() -> dict[str, str]:
    token = config.get_agent_secret_token()
    if not token:
        return {}
    return {"X-Agent-Token": token}


def upload_race(payload: dict, observer: Observer | None = None) -> tuple[bool, int | None]:
    """
    Synchronous upload from the agent worker thread.
    Returns (success, race_id).
    """
    session_uid = payload.get("session_uid")
    track_id = payload.get("track_id") or 0
    track_name = get_track_name(track_id) if track_id else "Unknown Track"

    cache_entry = local_cache.save(payload)
    _emit(
        observer,
        "cached",
        session_uid=session_uid,
        track_id=track_id,
        track_name=track_name,
        saved_at=cache_entry.get("saved_at"),
        pending_uploads=_pending_uploads_count(),
    )

    for attempt, delay in enumerate(RETRY_DELAYS + [None], start=1):
        cache_entry = local_cache.mark_attempt(session_uid) or cache_entry
        _emit(
            observer,
            "attempt",
            session_uid=session_uid,
            track_id=track_id,
            track_name=track_name,
            attempt=attempt,
            saved_at=cache_entry.get("saved_at"),
            last_attempt_at=cache_entry.get("last_attempt_at"),
            attempt_count=cache_entry.get("attempt_count"),
            target=SERVER_URL,
        )
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{SERVER_URL}/api/race/submit", json=payload, headers=_agent_headers())

            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") in ("ok", "duplicate"):
                    race_id = data.get("race_id")
                    telemetry_delivery.attach_race_id(session_uid, race_id)
                    local_cache.remove(session_uid)
                    print(f"[UPLOAD] Success: race_id={race_id}, round={data.get('round')}")
                    _emit(
                        observer,
                        "succeeded",
                        session_uid=session_uid,
                        track_id=track_id,
                        track_name=track_name,
                        race_id=race_id,
                        result=data.get("status"),
                        pending_uploads=_pending_uploads_count(),
                    )
                    return True, race_id

            if resp.status_code == 401:
                # Token rotation: retrying with the same token is pointless.
                # Surface to launcher so the user can re-enter a fresh token,
                # and keep the race cached for the next attempt.
                print("[UPLOAD] Agent token rejected (401)")
                local_cache.mark_failure(
                    session_uid,
                    "Agent token rejected (401)",
                    http_status=401,
                )
                _emit(
                    observer,
                    "auth_rejected",
                    session_uid=session_uid,
                    track_id=track_id,
                    track_name=track_name,
                    attempt=attempt,
                    pending_uploads=_pending_uploads_count(),
                )
                return False, None

            error_message = _extract_http_error(resp)
            cache_entry = local_cache.mark_failure(
                session_uid,
                error_message,
                http_status=resp.status_code,
            ) or cache_entry
            print(f"[UPLOAD] Attempt {attempt} failed: {error_message}")
            _emit(
                observer,
                "attempt_failed",
                session_uid=session_uid,
                track_id=track_id,
                track_name=track_name,
                attempt=attempt,
                error=error_message,
                last_attempt_at=cache_entry.get("last_attempt_at"),
                attempt_count=cache_entry.get("attempt_count"),
                pending_uploads=_pending_uploads_count(),
            )

        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            cache_entry = local_cache.mark_failure(session_uid, error_message) or cache_entry
            print(f"[UPLOAD] Attempt {attempt} error: {error_message}")
            _emit(
                observer,
                "attempt_failed",
                session_uid=session_uid,
                track_id=track_id,
                track_name=track_name,
                attempt=attempt,
                error=error_message,
                last_attempt_at=cache_entry.get("last_attempt_at"),
                attempt_count=cache_entry.get("attempt_count"),
                pending_uploads=_pending_uploads_count(),
            )

        if delay is not None:
            print(f"[UPLOAD] Retry in {delay}s...")
            _emit(
                observer,
                "retry_scheduled",
                session_uid=session_uid,
                track_id=track_id,
                track_name=track_name,
                attempt=attempt,
                retry_delay_s=delay,
                pending_uploads=_pending_uploads_count(),
            )
            time.sleep(delay)

    local_cache.mark_failure(session_uid, "All upload retries failed. Race stays cached locally.")
    print("[UPLOAD] All retries failed. Race cached for next launch.")
    _emit(
        observer,
        "exhausted",
        session_uid=session_uid,
        track_id=track_id,
        track_name=track_name,
        pending_uploads=_pending_uploads_count(),
        error="All upload retries failed. Race stays cached locally.",
    )
    return False, None


async def retry_pending_uploads(observer: Observer | None = None) -> None:
    """
    At startup, retry all locally cached races that failed earlier.
    """
    pending_entries = local_cache.load_all()
    _emit(observer, "retry_scan_complete", pending_uploads=len(pending_entries))
    if not pending_entries:
        return

    print(f"[UPLOAD] Found {len(pending_entries)} pending race(s) in cache")
    _emit(observer, "retry_queue_loaded", pending_uploads=len(pending_entries))
    for entry in pending_entries:
        payload = local_cache.get_payload(entry)
        uid = payload.get("session_uid")
        track_id = payload.get("track_id") or 0
        track_name = get_track_name(track_id) if track_id else "Unknown Track"
        print(f"[UPLOAD] Retrying cached race uid={uid}")
        _emit(
            observer,
            "retrying_cached",
            session_uid=uid,
            track_id=track_id,
            track_name=track_name,
            saved_at=entry.get("saved_at"),
            last_attempt_at=entry.get("last_attempt_at"),
            attempt_count=entry.get("attempt_count"),
            last_error=entry.get("last_error"),
            pending_uploads=_pending_uploads_count(),
        )
        success, _ = upload_race(payload, observer=observer)
        if not success:
            print("[UPLOAD] Still failed, will retry next launch")
            _emit(
                observer,
                "retry_deferred",
                session_uid=uid,
                track_id=track_id,
                track_name=track_name,
                pending_uploads=_pending_uploads_count(),
            )
