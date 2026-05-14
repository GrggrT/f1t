"""
Local cache for race-result uploads.

The cache keeps pending uploads on disk, records retry metadata, and uses
locked atomic writes so launcher-side manual retries and runtime uploads do
not corrupt each other.
"""
from __future__ import annotations

import copy
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import CACHE_FILE


CACHE_SCHEMA_VERSION = 2
CACHE_BACKUP_FILE = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.bak")
CACHE_TEMP_FILE = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.tmp")

_CACHE_LOCK = threading.RLock()
_METADATA_KEYS = {
    "cache_version",
    "session_uid",
    "saved_at",
    "updated_at",
    "last_attempt_at",
    "attempt_count",
    "last_error",
    "last_http_status",
    "last_outcome",
    "race_id",
    "payload",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _session_uid_key(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _cache_sort_key(entry: dict) -> tuple[str, str]:
    return (entry.get("saved_at") or "", _session_uid_key(entry.get("session_uid")) or "")


def _payload_from_record(record: dict) -> dict:
    if isinstance(record.get("payload"), dict):
        payload = record["payload"]
    else:
        payload = {key: value for key, value in record.items() if key not in _METADATA_KEYS}
    return copy.deepcopy(payload)


def _normalize_entry(record: Any) -> dict | None:
    if not isinstance(record, dict):
        return None

    payload = _payload_from_record(record)
    session_uid = payload.get("session_uid") or record.get("session_uid")
    if session_uid is None:
        return None

    payload["session_uid"] = session_uid
    saved_at = record.get("saved_at") or _now_iso()
    updated_at = record.get("updated_at") or saved_at

    return {
        "cache_version": CACHE_SCHEMA_VERSION,
        "session_uid": session_uid,
        "saved_at": saved_at,
        "updated_at": updated_at,
        "last_attempt_at": record.get("last_attempt_at"),
        "attempt_count": _safe_int(record.get("attempt_count"), 0),
        "last_error": record.get("last_error"),
        "last_http_status": record.get("last_http_status"),
        "last_outcome": record.get("last_outcome") or "pending",
        "race_id": record.get("race_id"),
        "payload": payload,
    }


def _normalize_entries(records: Any) -> list[dict]:
    if not isinstance(records, list):
        raise ValueError("Cache root must be a list")

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
    if not CACHE_FILE.exists():
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    target = CACHE_FILE.with_name(f"{CACHE_FILE.stem}.corrupt-{stamp}{CACHE_FILE.suffix}")
    try:
        CACHE_FILE.replace(target)
        print(f"[CACHE] Quarantined corrupt cache file to {target.name}")
    except Exception as exc:
        print(f"[CACHE] Failed to quarantine corrupt cache: {exc}")


def _write_entries_locked(entries: list[dict], *, refresh_backup: bool = True) -> None:
    serialized = json.dumps(entries, ensure_ascii=False, indent=2)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_TEMP_FILE.write_text(serialized, encoding="utf-8")

    if refresh_backup and CACHE_FILE.exists():
        try:
            shutil.copyfile(CACHE_FILE, CACHE_BACKUP_FILE)
        except Exception as exc:
            print(f"[CACHE] Failed to refresh backup: {exc}")

    CACHE_TEMP_FILE.replace(CACHE_FILE)


def _load_entries_locked() -> list[dict]:
    candidates = [CACHE_FILE, CACHE_BACKUP_FILE, CACHE_TEMP_FILE]
    errors: list[str] = []

    for path in candidates:
        if not path.exists():
            continue

        try:
            entries = _read_entries_from_path(path)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        if path != CACHE_FILE:
            _quarantine_corrupt_primary()
            try:
                _write_entries_locked(entries, refresh_backup=False)
                print(f"[CACHE] Restored cache from {path.name}")
            except Exception as exc:
                print(f"[CACHE] Failed to restore cache from {path.name}: {exc}")

        return entries

    if errors:
        print(f"[CACHE] Failed to read cache candidates: {'; '.join(errors)}")
    return []


def _find_entry_index(entries: list[dict], session_uid: Any) -> int | None:
    key = _session_uid_key(session_uid)
    if key is None:
        return None

    for index, entry in enumerate(entries):
        if _session_uid_key(entry.get("session_uid")) == key:
            return index
    return None


def _copy_entry(entry: dict | None) -> dict | None:
    if entry is None:
        return None
    return copy.deepcopy(entry)


def save(race_payload: dict) -> dict:
    """Upsert a race payload into the local cache."""
    session_uid = race_payload.get("session_uid")
    now = _now_iso()

    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)

        if index is None:
            entry = {
                "cache_version": CACHE_SCHEMA_VERSION,
                "session_uid": session_uid,
                "saved_at": now,
                "updated_at": now,
                "last_attempt_at": None,
                "attempt_count": 0,
                "last_error": None,
                "last_http_status": None,
                "last_outcome": "pending",
                "race_id": None,
                "payload": copy.deepcopy(race_payload),
            }
            entries.append(entry)
            action = "Saved"
        else:
            existing = entries[index]
            entry = {
                **existing,
                "session_uid": session_uid,
                "updated_at": now,
                "payload": copy.deepcopy(race_payload),
            }
            entries[index] = entry
            action = "Updated"

        entries.sort(key=_cache_sort_key)
        _write_entries_locked(entries)
        print(f"[CACHE] {action} race uid={session_uid}, total pending: {len(entries)}")
        return _copy_entry(entry) or {}


def load_all() -> list[dict]:
    """Return all pending uploads in normalized cache-entry form."""
    with _CACHE_LOCK:
        return [_copy_entry(entry) or {} for entry in _load_entries_locked()]


def get_payload(entry: dict) -> dict:
    normalized = _normalize_entry(entry)
    return copy.deepcopy(normalized["payload"]) if normalized else {}


def mark_attempt(session_uid: Any) -> dict | None:
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)
        if index is None:
            return None

        entry = entries[index]
        entry["attempt_count"] = _safe_int(entry.get("attempt_count"), 0) + 1
        entry["last_attempt_at"] = _now_iso()
        entry["updated_at"] = entry["last_attempt_at"]
        entry["last_outcome"] = "retrying"
        _write_entries_locked(entries)
        return _copy_entry(entry)


def mark_failure(session_uid: Any, error: str, *, http_status: int | None = None) -> dict | None:
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        index = _find_entry_index(entries, session_uid)
        if index is None:
            return None

        entry = entries[index]
        entry["updated_at"] = _now_iso()
        entry["last_outcome"] = "failed"
        entry["last_error"] = error
        entry["last_http_status"] = http_status
        _write_entries_locked(entries)
        return _copy_entry(entry)


def remove(session_uid: Any) -> bool:
    """Remove a cached race after a confirmed successful or duplicate-safe upload."""
    with _CACHE_LOCK:
        entries = _load_entries_locked()
        remaining = [
            entry for entry in entries
            if _session_uid_key(entry.get("session_uid")) != _session_uid_key(session_uid)
        ]

        if len(remaining) == len(entries):
            return False

        _write_entries_locked(remaining)
        print(f"[CACHE] Removed uid={session_uid}, remaining: {len(remaining)}")
        return True


def pending_count() -> int:
    return len(load_all())


def has_pending() -> bool:
    return pending_count() > 0
