"""
Persistent telemetry snapshot delivery.

Telemetry is cached by session_uid before race upload completes, then flushed
only after the backend has returned a race_id. Failed telemetry flushes remain
durably cached and are retried on the next runtime start.
"""
from __future__ import annotations

import copy
import json
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from agent.config import AGENT_SECRET_TOKEN, RETRY_DELAYS, SERVER_URL, TELEMETRY_CACHE_FILE
from agent.telemetry_buffer import TelemetrySnapshot


Observer = Callable[[str, dict], None]

CACHE_SCHEMA_VERSION = 1
CACHE_BACKUP_FILE = TELEMETRY_CACHE_FILE.with_suffix(f"{TELEMETRY_CACHE_FILE.suffix}.bak")
CACHE_TEMP_FILE = TELEMETRY_CACHE_FILE.with_suffix(f"{TELEMETRY_CACHE_FILE.suffix}.tmp")
ORPHAN_ARCHIVE_FILE = TELEMETRY_CACHE_FILE.with_name("telemetry_orphan_archive.json")

_CACHE_LOCK = threading.RLock()


def _emit(observer: Observer | None, event: str, **payload) -> None:
    if not observer:
        return
    try:
        observer(event, payload)
    except Exception:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _session_uid_key(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _copy_entry(entry: dict | None) -> dict | None:
    return copy.deepcopy(entry) if entry is not None else None


def _cache_sort_key(entry: dict) -> tuple[str, str]:
    return (entry.get("saved_at") or "", _session_uid_key(entry.get("session_uid")) or "")


def _normalize_entry(record: Any) -> dict | None:
    if not isinstance(record, dict):
        return None
    session_uid = record.get("session_uid")
    if session_uid is None:
        return None
    snapshot = TelemetrySnapshot.from_payload(record.get("snapshot"))
    if not snapshot.has_data():
        return None

    saved_at = record.get("saved_at") or _now_iso()
    updated_at = record.get("updated_at") or saved_at
    return {
        "cache_version": CACHE_SCHEMA_VERSION,
        "session_uid": session_uid,
        "race_id": _safe_int(record.get("race_id")),
        "saved_at": saved_at,
        "updated_at": updated_at,
        "last_attempt_at": record.get("last_attempt_at"),
        "attempt_count": int(record.get("attempt_count", 0) or 0),
        "last_error": record.get("last_error"),
        "last_http_status": record.get("last_http_status"),
        "last_outcome": record.get("last_outcome") or "pending",
        "snapshot": snapshot.to_payload(),
    }


def _normalize_entries(records: Any) -> list[dict]:
    if not isinstance(records, list):
        raise ValueError("Telemetry cache root must be a list")

    deduped: dict[str, dict] = {}
    for record in records:
        entry = _normalize_entry(record)
        if entry is None:
            continue
        key = _session_uid_key(entry.get("session_uid"))
        if key is None:
            continue
        deduped[key] = entry
    return sorted(deduped.values(), key=_cache_sort_key)


def _read_entries_from_path(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _normalize_entries(raw)


def _quarantine_corrupt_primary() -> None:
    if not TELEMETRY_CACHE_FILE.exists():
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    target = TELEMETRY_CACHE_FILE.with_name(f"{TELEMETRY_CACHE_FILE.stem}.corrupt-{stamp}{TELEMETRY_CACHE_FILE.suffix}")
    try:
        TELEMETRY_CACHE_FILE.replace(target)
        print(f"[TELEM] Quarantined corrupt telemetry cache to {target.name}")
    except Exception as exc:
        print(f"[TELEM] Failed to quarantine telemetry cache: {exc}")


def _write_entries_locked(entries: list[dict], *, refresh_backup: bool = True) -> None:
    serialized = json.dumps(entries, ensure_ascii=False, indent=2)
    TELEMETRY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_TEMP_FILE.write_text(serialized, encoding="utf-8")

    if refresh_backup and TELEMETRY_CACHE_FILE.exists():
        try:
            shutil.copyfile(TELEMETRY_CACHE_FILE, CACHE_BACKUP_FILE)
        except Exception as exc:
            print(f"[TELEM] Failed to refresh telemetry cache backup: {exc}")

    CACHE_TEMP_FILE.replace(TELEMETRY_CACHE_FILE)


def _load_entries_locked() -> list[dict]:
    candidates = [TELEMETRY_CACHE_FILE, CACHE_BACKUP_FILE, CACHE_TEMP_FILE]
    errors: list[str] = []

    for path in candidates:
        if not path.exists():
            continue
        try:
            entries = _read_entries_from_path(path)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        if path != TELEMETRY_CACHE_FILE:
            _quarantine_corrupt_primary()
            try:
                _write_entries_locked(entries, refresh_backup=False)
                print(f"[TELEM] Restored telemetry cache from {path.name}")
            except Exception as exc:
                print(f"[TELEM] Failed to restore telemetry cache from {path.name}: {exc}")
        return entries

    if errors:
        print(f"[TELEM] Failed to read telemetry cache candidates: {'; '.join(errors)}")
    return []


def _find_entry_index(entries: list[dict], session_uid: Any) -> int | None:
    key = _session_uid_key(session_uid)
    if key is None:
        return None
    for index, entry in enumerate(entries):
        if _session_uid_key(entry.get("session_uid")) == key:
            return index
    return None


def _extract_http_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    detail = None
    if isinstance(payload, dict):
        detail = payload.get("message") or payload.get("detail") or payload.get("error") or payload.get("reason")
    if detail:
        return f"HTTP {response.status_code}: {detail}"
    return f"HTTP {response.status_code}"


def _agent_headers() -> dict[str, str]:
    if not AGENT_SECRET_TOKEN:
        return {}
    return {"X-Agent-Token": AGENT_SECRET_TOKEN}


def _load_archive_locked() -> list[dict]:
    if not ORPHAN_ARCHIVE_FILE.exists():
        return []
    try:
        raw = json.loads(ORPHAN_ARCHIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def _write_archive_locked(entries: list[dict]) -> None:
    ORPHAN_ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = ORPHAN_ARCHIVE_FILE.with_suffix(f"{ORPHAN_ARCHIVE_FILE.suffix}.tmp")
    temp_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(ORPHAN_ARCHIVE_FILE)


def load_all() -> list[dict]:
    with _CACHE_LOCK:
        return [_copy_entry(entry) or {} for entry in _load_entries_locked()]


def pending_count() -> int:
    return len(load_all())


def save_snapshot(session_uid: int, snapshot: TelemetrySnapshot) -> dict | None:
    finalized = snapshot.finalize()
    if not finalized.has_data():
        return None

    now = _now_iso()
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)
        entry = {
            "cache_version": CACHE_SCHEMA_VERSION,
            "session_uid": session_uid,
            "race_id": entries[index].get("race_id") if index is not None else None,
            "saved_at": entries[index].get("saved_at", now) if index is not None else now,
            "updated_at": now,
            "last_attempt_at": None,
            "attempt_count": 0,
            "last_error": None,
            "last_http_status": None,
            "last_outcome": "pending",
            "snapshot": finalized.to_payload(),
        }
        if index is None:
            entries.append(entry)
            action = "Saved"
        else:
            entries[index] = entry
            action = "Updated"
        entries.sort(key=_cache_sort_key)
        _write_entries_locked(entries)
        print(f"[TELEM] {action} snapshot uid={session_uid}, pending: {len(entries)}")
        return _copy_entry(entry)


def attach_race_id(session_uid: int, race_id: int | None) -> dict | None:
    if not race_id:
        return None
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)
        if index is None:
            return None
        entry = entries[index]
        entry["race_id"] = int(race_id)
        entry["updated_at"] = _now_iso()
        entry["last_outcome"] = "race_uploaded"
        _write_entries_locked(entries)
        return _copy_entry(entry)


def remove(session_uid: int) -> bool:
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        remaining = [
            entry
            for entry in entries
            if _session_uid_key(entry.get("session_uid")) != _session_uid_key(session_uid)
        ]
        if len(remaining) == len(entries):
            return False
        _write_entries_locked(remaining)
        print(f"[TELEM] Removed cached telemetry uid={session_uid}, remaining: {len(remaining)}")
        return True


def quarantine(session_uid: int, *, reason: str) -> dict | None:
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)
        if index is None:
            return None

        entry = _copy_entry(entries[index]) or {}
        remaining = [
            item
            for item in entries
            if _session_uid_key(item.get("session_uid")) != _session_uid_key(session_uid)
        ]
        archive = _load_archive_locked()
        archived = {
            "session_uid": session_uid,
            "reason": reason,
            "quarantined_at": _now_iso(),
            "entry": entry,
        }
        archive.append(archived)
        _write_archive_locked(archive)
        _write_entries_locked(remaining)
        print(f"[TELEM] Quarantined orphaned telemetry uid={session_uid}, remaining: {len(remaining)}")
        return archived


def _mark_attempt_locked(entries: list[dict], index: int) -> dict:
    entry = entries[index]
    entry["attempt_count"] = int(entry.get("attempt_count", 0) or 0) + 1
    entry["last_attempt_at"] = _now_iso()
    entry["updated_at"] = entry["last_attempt_at"]
    entry["last_outcome"] = "retrying"
    _write_entries_locked(entries)
    return _copy_entry(entry) or {}


def _mark_failure_locked(entries: list[dict], index: int, error: str, *, http_status: int | None = None) -> dict:
    entry = entries[index]
    entry["updated_at"] = _now_iso()
    entry["last_outcome"] = "failed"
    entry["last_error"] = error
    entry["last_http_status"] = http_status
    _write_entries_locked(entries)
    return _copy_entry(entry) or {}


def _post_snapshot(race_id: int, snapshot: TelemetrySnapshot) -> None:
    payload = snapshot.to_payload()
    with httpx.Client(timeout=30) as client:
        if payload["session_history"]:
            response = client.post(
                f"{SERVER_URL}/api/telemetry/session-history",
                json={
                    "race_id": race_id,
                    "vehicles": payload["session_history"],
                },
                headers=_agent_headers(),
            )
            if response.status_code != 200:
                raise RuntimeError(_extract_http_error(response))

        for lap in payload["laps"]:
            response = client.post(
                f"{SERVER_URL}/api/telemetry/submit",
                json={
                    "race_id": race_id,
                    "vehicle_index": lap["vehicle_index"],
                    "lap_number": lap["lap_number"],
                    "lap_time_ms": lap.get("lap_time_ms"),
                    "samples": lap["samples"],
                },
                headers=_agent_headers(),
            )
            if response.status_code != 200:
                raise RuntimeError(_extract_http_error(response))


def _resolve_race_id_from_backend(session_uid: int, observer: Observer | None = None) -> int | None:
    with httpx.Client(timeout=15) as client:
        response = client.get(
            f"{SERVER_URL}/api/race/session/{session_uid}",
            headers=_agent_headers(),
        )

    if response.status_code == 404:
        _emit(
            observer,
            "race_id_lookup_missing",
            session_uid=session_uid,
            pending_flushes=pending_count(),
        )
        return None
    if response.status_code != 200:
        raise RuntimeError(_extract_http_error(response))

    payload = response.json()
    race_id = _safe_int(payload.get("race_id")) if isinstance(payload, dict) else None
    if race_id is None:
        return None

    attach_race_id(session_uid, race_id)
    _emit(
        observer,
        "race_id_resolved",
        session_uid=session_uid,
        race_id=race_id,
        pending_flushes=pending_count(),
    )
    return race_id


def flush_pending(session_uid: int, race_id: int | None = None, observer: Observer | None = None) -> bool:
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)
        if index is None:
            return True
        if race_id:
            entries[index]["race_id"] = int(race_id)
            entries[index]["updated_at"] = _now_iso()
            entries[index]["last_outcome"] = "race_uploaded"
            _write_entries_locked(entries)
        entry = _copy_entry(entries[index]) or {}

    snapshot = TelemetrySnapshot.from_payload(entry.get("snapshot"))
    if not snapshot.has_data():
        remove(session_uid)
        return True

    effective_race_id = _safe_int(entry.get("race_id"))
    if effective_race_id is None:
        try:
            effective_race_id = _resolve_race_id_from_backend(int(session_uid), observer=observer)
        except Exception as exc:
            _emit(
                observer,
                "blocked_no_race_id",
                session_uid=session_uid,
                error=f"Failed to resolve race_id from backend: {str(exc) or exc.__class__.__name__}",
                pending_flushes=pending_count(),
            )
            return False
    if effective_race_id is None:
        _emit(
            observer,
            "blocked_no_race_id",
            session_uid=session_uid,
            pending_flushes=pending_count(),
        )
        return False

    total_laps = snapshot.lap_count()
    for attempt, delay in enumerate(RETRY_DELAYS + [None], start=1):
        with _CACHE_LOCK:
            entries = _load_entries_locked()
            index = _find_entry_index(entries, session_uid)
            if index is None:
                return True
            entry = _mark_attempt_locked(entries, index)

        _emit(
            observer,
            "attempt",
            session_uid=session_uid,
            race_id=effective_race_id,
            attempt=attempt,
            lap_count=total_laps,
            vehicle_history_count=len(snapshot.session_history),
            last_attempt_at=entry.get("last_attempt_at"),
            attempt_count=entry.get("attempt_count"),
            pending_flushes=pending_count(),
        )

        try:
            _post_snapshot(effective_race_id, snapshot)
            remove(session_uid)
            print(f"[TELEM] Snapshot uid={session_uid} flushed for race_id={effective_race_id}")
            _emit(
                observer,
                "succeeded",
                session_uid=session_uid,
                race_id=effective_race_id,
                lap_count=total_laps,
                vehicle_history_count=len(snapshot.session_history),
                pending_flushes=pending_count(),
            )
            return True
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            with _CACHE_LOCK:
                entries = _load_entries_locked()
                index = _find_entry_index(entries, session_uid)
                if index is None:
                    return False
                entry = _mark_failure_locked(entries, index, error_message)
            print(f"[TELEM] Flush attempt {attempt} failed for uid={session_uid}: {error_message}")
            _emit(
                observer,
                "attempt_failed",
                session_uid=session_uid,
                race_id=effective_race_id,
                attempt=attempt,
                error=error_message,
                last_attempt_at=entry.get("last_attempt_at"),
                attempt_count=entry.get("attempt_count"),
                pending_flushes=pending_count(),
            )

        if delay is not None:
            _emit(
                observer,
                "retry_scheduled",
                session_uid=session_uid,
                race_id=effective_race_id,
                attempt=attempt,
                retry_delay_s=delay,
                pending_flushes=pending_count(),
            )
            time.sleep(delay)

    _emit(
        observer,
        "exhausted",
        session_uid=session_uid,
        race_id=effective_race_id,
        error="Telemetry flush retries exhausted; snapshot stays cached locally.",
        pending_flushes=pending_count(),
    )
    return False


async def retry_pending(observer: Observer | None = None) -> None:
    entries = load_all()
    _emit(observer, "retry_scan_complete", pending_flushes=len(entries))
    if not entries:
        return

    for entry in entries:
        session_uid = entry.get("session_uid")
        if session_uid is None:
            continue
        flush_pending(
            int(session_uid),
            race_id=_safe_int(entry.get("race_id")),
            observer=observer,
        )
