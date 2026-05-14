from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agent import local_cache, telemetry_delivery
from agent.config import CACHE_FILE, DATA_DIR, RAW_LOG_DIR, TELEMETRY_CACHE_FILE
from agent.replay_harness import analyze_raw_log


SEVERITY_ORDER = {
    "error": 0,
    "warn": 1,
    "info": 2,
}


def _path_candidates(primary: Path) -> list[Path]:
    return [
        primary,
        primary.with_suffix(f"{primary.suffix}.bak"),
        primary.with_suffix(f"{primary.suffix}.tmp"),
    ]


def _safe_iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()


def _load_cache_entries(
    primary_path: Path,
    normalize: Callable[[Any], list[dict]],
) -> tuple[list[dict], dict]:
    errors: list[str] = []
    for candidate in _path_candidates(primary_path):
        if not candidate.exists():
            continue
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
            entries = normalize(raw)
        except Exception as exc:
            errors.append(f"{candidate.name}: {exc}")
            continue
        return entries, {"source": str(candidate), "errors": errors}
    return [], {"source": None, "errors": errors}


def _normalize_race_entry(entry: dict) -> dict:
    payload = local_cache.get_payload(entry)
    return {
        "session_uid": payload.get("session_uid"),
        "season_id": payload.get("season_id"),
        "track_id": payload.get("track_id"),
        "saved_at": entry.get("saved_at"),
        "updated_at": entry.get("updated_at"),
        "last_attempt_at": entry.get("last_attempt_at"),
        "attempt_count": int(entry.get("attempt_count", 0) or 0),
        "last_error": entry.get("last_error"),
        "last_http_status": entry.get("last_http_status"),
        "last_outcome": entry.get("last_outcome"),
        "participants_count": len(payload.get("participants") or []),
        "total_laps": payload.get("total_laps"),
    }


def _normalize_telemetry_entry(entry: dict) -> dict:
    snapshot = entry.get("snapshot") or {}
    laps = [lap for lap in snapshot.get("laps", []) if isinstance(lap, dict)]
    session_history = [item for item in snapshot.get("session_history", []) if isinstance(item, dict)]
    sample_count = sum(len(lap.get("samples") or []) for lap in laps)
    race_id = entry.get("race_id")
    waiting_for_race_id = race_id in (None, "", 0, "0")
    return {
        "session_uid": entry.get("session_uid"),
        "race_id": race_id if not waiting_for_race_id else None,
        "saved_at": entry.get("saved_at"),
        "updated_at": entry.get("updated_at"),
        "last_attempt_at": entry.get("last_attempt_at"),
        "attempt_count": int(entry.get("attempt_count", 0) or 0),
        "last_error": entry.get("last_error"),
        "last_http_status": entry.get("last_http_status"),
        "last_outcome": entry.get("last_outcome"),
        "lap_count": len(laps),
        "sample_count": sample_count,
        "vehicle_history_count": len(session_history),
        "waiting_for_race_id": waiting_for_race_id,
    }


def _collect_raw_logs(raw_log_dir: Path, *, max_logs: int, analyze_logs: bool) -> list[dict]:
    if not raw_log_dir.exists():
        return []

    files = sorted(
        (path for path in raw_log_dir.glob("session_*.bin") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if max_logs > 0:
        files = files[:max_logs]

    entries: list[dict] = []
    for path in files:
        stat = path.stat()
        entry = {
            "path": str(path),
            "size_bytes": stat.st_size,
            "modified_at": _safe_iso_from_timestamp(stat.st_mtime),
            "session_uids": [],
            "total_packets": None,
            "parse_failures": None,
            "extractor_hits": None,
            "replay_command": f'python -m agent.replay_harness --log "{path}" --agent',
            "analyzed": analyze_logs,
        }
        if analyze_logs:
            try:
                summary = analyze_raw_log(path)
            except Exception as exc:
                entry["analysis_error"] = str(exc) or exc.__class__.__name__
            else:
                entry["session_uids"] = [int(value) for value in summary.sessions]
                entry["total_packets"] = summary.total_packets
                entry["parse_failures"] = list(summary.parse_failures)
                entry["extractor_hits"] = dict(summary.extractor_hits)
        entries.append(entry)
    return entries


def _latest_timestamp(session: dict) -> str:
    for candidate in (
        ((session.get("telemetry") or {}).get("updated_at")),
        ((session.get("race_upload") or {}).get("updated_at")),
        ((session.get("raw_log") or {}).get("modified_at")),
        ((session.get("telemetry") or {}).get("saved_at")),
        ((session.get("race_upload") or {}).get("saved_at")),
    ):
        if candidate:
            return str(candidate)
    return ""


def _classify_session(session_uid: int, session: dict) -> dict:
    race_upload = session.get("race_upload")
    telemetry = session.get("telemetry")
    raw_log = session.get("raw_log")

    if race_upload:
        return {
            "session_uid": session_uid,
            "status": "race_upload_pending",
            "severity": "warn",
            "summary": "Race result upload is still cached locally.",
            "recommended_action": (
                "Bring the backend back online, then retry cached delivery from the launcher "
                "or restart the agent to replay pending uploads automatically."
            ),
            "race_upload": race_upload,
            "telemetry": telemetry,
            "raw_log": raw_log,
        }

    if telemetry:
        if telemetry.get("race_id"):
            return {
                "session_uid": session_uid,
                "status": "telemetry_flush_pending",
                "severity": "warn",
                "summary": "Race upload succeeded, but telemetry flush is still pending.",
                "recommended_action": (
                    "Retry buffered delivery. The race_id is already known, so the telemetry snapshot "
                    "should flush as soon as the telemetry endpoint is reachable again."
                ),
                "race_upload": None,
                "telemetry": telemetry,
                "raw_log": raw_log,
            }
        if raw_log:
            return {
                "session_uid": session_uid,
                "status": "telemetry_waiting_for_race_id",
                "severity": "warn",
                "summary": "Telemetry snapshot is cached locally but still has no race_id.",
                "recommended_action": (
                    "Check whether the matching race submit reached the backend. If the session is missing "
                    "server-side, replay the raw log and rebuild the race pipeline from the captured packets."
                ),
                "race_upload": None,
                "telemetry": telemetry,
                "raw_log": raw_log,
            }
        return {
            "session_uid": session_uid,
            "status": "orphaned_telemetry",
            "severity": "error",
            "summary": "Telemetry snapshot is stranded locally without race_id and without a raw log.",
            "recommended_action": (
                "Try telemetry retry once more to resolve race_id from backend. If the session is still missing "
                "server-side, quarantine the orphaned telemetry entry so it no longer blocks race-day diagnostics."
            ),
            "race_upload": None,
            "telemetry": telemetry,
            "raw_log": None,
        }

    return {
        "session_uid": session_uid,
        "status": "raw_log_available",
        "severity": "info",
        "summary": "Raw log is available for replay if this session needs investigation.",
        "recommended_action": (
            "Use the replay command to inspect parser/runtime behavior for this capture if a backend or "
            "race-day incident needs reconstruction."
        ),
        "race_upload": None,
        "telemetry": None,
        "raw_log": raw_log,
    }


def build_postmortem_report(
    *,
    data_dir: str | Path | None = None,
    max_raw_logs: int = 10,
    analyze_raw_logs: bool = True,
) -> dict:
    resolved_data_dir = Path(data_dir) if data_dir else DATA_DIR
    race_cache_file = resolved_data_dir / CACHE_FILE.name
    telemetry_cache_file = resolved_data_dir / TELEMETRY_CACHE_FILE.name
    raw_log_dir = resolved_data_dir / RAW_LOG_DIR.name

    race_entries_raw, race_meta = _load_cache_entries(race_cache_file, local_cache._normalize_entries)
    telemetry_entries_raw, telemetry_meta = _load_cache_entries(
        telemetry_cache_file,
        telemetry_delivery._normalize_entries,
    )

    race_entries = [_normalize_race_entry(entry) for entry in race_entries_raw]
    telemetry_entries = [_normalize_telemetry_entry(entry) for entry in telemetry_entries_raw]
    raw_logs = _collect_raw_logs(raw_log_dir, max_logs=max_raw_logs, analyze_logs=analyze_raw_logs)

    sessions: dict[int, dict[str, Any]] = {}

    def ensure_session(session_uid: Any) -> dict | None:
        try:
            normalized = int(session_uid)
        except (TypeError, ValueError):
            return None
        return sessions.setdefault(normalized, {"race_upload": None, "telemetry": None, "raw_log": None})

    for entry in race_entries:
        session = ensure_session(entry.get("session_uid"))
        if session is not None:
            session["race_upload"] = entry

    for entry in telemetry_entries:
        session = ensure_session(entry.get("session_uid"))
        if session is not None:
            session["telemetry"] = entry

    for entry in raw_logs:
        for session_uid in entry.get("session_uids") or []:
            session = ensure_session(session_uid)
            if session is None:
                continue
            if session.get("raw_log") is None:
                session["raw_log"] = entry

    classified_sessions = [_classify_session(session_uid, payload) for session_uid, payload in sessions.items()]
    classified_sessions.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item.get("severity", "info"), 99),
            _latest_timestamp(item),
        ),
        reverse=False,
    )

    telemetry_waiting_for_race_id = sum(1 for entry in telemetry_entries if entry["waiting_for_race_id"])
    telemetry_ready_to_flush = len(telemetry_entries) - telemetry_waiting_for_race_id
    issue_count = sum(1 for item in classified_sessions if item.get("severity") in {"warn", "error"})

    report = {
        "data_dir": str(resolved_data_dir),
        "race_cache": {
            "count": len(race_entries),
            "source": race_meta.get("source"),
            "errors": race_meta.get("errors", []),
            "entries": race_entries,
        },
        "telemetry_cache": {
            "count": len(telemetry_entries),
            "waiting_for_race_id": telemetry_waiting_for_race_id,
            "ready_to_flush": telemetry_ready_to_flush,
            "source": telemetry_meta.get("source"),
            "errors": telemetry_meta.get("errors", []),
            "entries": telemetry_entries,
        },
        "raw_logs": {
            "count": len(raw_logs),
            "dir": str(raw_log_dir),
            "entries": raw_logs,
            "analysis_enabled": analyze_raw_logs,
        },
        "summary": {
            "issue_count": issue_count,
            "pending_race_uploads": len(race_entries),
            "pending_telemetry": len(telemetry_entries),
            "pending_telemetry_waiting_for_race_id": telemetry_waiting_for_race_id,
            "pending_telemetry_ready_to_flush": telemetry_ready_to_flush,
            "raw_logs": len(raw_logs),
        },
        "sessions": classified_sessions,
        "commands": {
            "inspect": "python -m agent.postmortem --json",
            "replay": raw_logs[0]["replay_command"] if raw_logs else None,
            "quarantine_orphans": "python -m agent.postmortem --quarantine-orphaned-telemetry --json",
        },
    }
    return report


def quarantine_orphaned_telemetry(
    report: dict | None = None,
    *,
    data_dir: str | Path | None = None,
) -> list[dict]:
    active_report = report or build_postmortem_report(data_dir=data_dir)
    resolved_data_dir = Path(data_dir) if data_dir else None
    if resolved_data_dir is None:
        return _quarantine_orphaned_sessions(active_report)

    from unittest import mock

    telemetry_cache_file = resolved_data_dir / TELEMETRY_CACHE_FILE.name
    with mock.patch.object(telemetry_delivery, "TELEMETRY_CACHE_FILE", telemetry_cache_file):
        with mock.patch.object(
            telemetry_delivery,
            "CACHE_BACKUP_FILE",
            telemetry_cache_file.with_suffix(f"{telemetry_cache_file.suffix}.bak"),
        ):
            with mock.patch.object(
                telemetry_delivery,
                "CACHE_TEMP_FILE",
                telemetry_cache_file.with_suffix(f"{telemetry_cache_file.suffix}.tmp"),
            ):
                with mock.patch.object(
                    telemetry_delivery,
                    "ORPHAN_ARCHIVE_FILE",
                    telemetry_cache_file.with_name("telemetry_orphan_archive.json"),
                ):
                    return _quarantine_orphaned_sessions(active_report)


def _quarantine_orphaned_sessions(report: dict) -> list[dict]:
    quarantined: list[dict] = []
    for session in report.get("sessions") or []:
        if session.get("status") != "orphaned_telemetry":
            continue
        session_uid = session.get("session_uid")
        if session_uid is None:
            continue
        archived = telemetry_delivery.quarantine(
            int(session_uid),
            reason="quarantined_by_postmortem_tool",
        )
        if archived is not None:
            quarantined.append(archived)
    return quarantined


def _print_text_report(report: dict) -> None:
    summary = report["summary"]
    print(f"Data dir: {report['data_dir']}")
    print(f"Race uploads pending: {summary['pending_race_uploads']}")
    print(
        "Telemetry pending: "
        f"{summary['pending_telemetry']} "
        f"(waiting_for_race_id={summary['pending_telemetry_waiting_for_race_id']}, "
        f"ready_to_flush={summary['pending_telemetry_ready_to_flush']})"
    )
    print(f"Raw logs scanned: {summary['raw_logs']}")
    print(f"Sessions needing attention: {summary['issue_count']}")

    sessions = report.get("sessions") or []
    if not sessions:
        print("No cached sessions or raw logs were found.")
        return

    print("")
    print("Session summary:")
    for session in sessions:
        print(
            f"- uid={session['session_uid']} "
            f"status={session['status']} severity={session['severity']}"
        )
        print(f"  summary: {session['summary']}")
        print(f"  next: {session['recommended_action']}")
        raw_log = session.get("raw_log")
        if raw_log:
            print(f"  raw_log: {raw_log['path']}")
            print(f"  replay: {raw_log['replay_command']}")
        telemetry = session.get("telemetry")
        if telemetry:
            print(
                "  telemetry: "
                f"race_id={telemetry.get('race_id')} "
                f"laps={telemetry.get('lap_count')} "
                f"samples={telemetry.get('sample_count')} "
                f"last_error={telemetry.get('last_error')}"
            )
        race_upload = session.get("race_upload")
        if race_upload:
            print(
                "  race_upload: "
                f"participants={race_upload.get('participants_count')} "
                f"attempts={race_upload.get('attempt_count')} "
                f"last_error={race_upload.get('last_error')}"
            )
    remediation = report.get("remediation") or {}
    quarantined = remediation.get("quarantined_orphaned_telemetry") or []
    if quarantined:
        print("")
        print(f"Quarantined orphaned telemetry entries: {len(quarantined)}")
        for entry in quarantined:
            print(f"- uid={entry.get('session_uid')} reason={entry.get('reason')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local agent artifacts for race-day postmortem.")
    parser.add_argument("--data-dir", type=Path, help="Override the agent data directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    parser.add_argument("--max-raw-logs", type=int, default=10, help="Limit how many raw logs to inspect.")
    parser.add_argument(
        "--quarantine-orphaned-telemetry",
        action="store_true",
        help="Archive orphaned telemetry entries so they no longer remain in the active retry queue.",
    )
    parser.add_argument(
        "--skip-raw-log-analysis",
        action="store_true",
        help="List raw logs without replay-parser analysis.",
    )
    args = parser.parse_args()

    report = build_postmortem_report(
        data_dir=args.data_dir,
        max_raw_logs=max(args.max_raw_logs, 0),
        analyze_raw_logs=not args.skip_raw_log_analysis,
    )
    if args.quarantine_orphaned_telemetry:
        remediation = {
            "quarantined_orphaned_telemetry": quarantine_orphaned_telemetry(
                report,
                data_dir=args.data_dir,
            ),
        }
        report = build_postmortem_report(
            data_dir=args.data_dir,
            max_raw_logs=max(args.max_raw_logs, 0),
            analyze_raw_logs=not args.skip_raw_log_analysis,
        )
        report["remediation"] = remediation

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
