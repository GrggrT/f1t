from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent.postmortem import build_postmortem_report, quarantine_orphaned_telemetry
from agent.replay_harness import write_sample_raw_log
from agent.telemetry_buffer import TelemetrySnapshot


class PostmortemToolingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="f1t_postmortem_")
        self.addCleanup(self._tmp_dir.cleanup)
        self.data_dir = Path(self._tmp_dir.name)
        (self.data_dir / "raw_logs").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _race_payload(session_uid: int) -> dict:
        return {
            "season_id": 7,
            "session_uid": session_uid,
            "packet_format": 2025,
            "track_id": 10,
            "weather_start": 0,
            "weather_end": 0,
            "total_laps": 5,
            "air_temp": 24,
            "track_temp": 31,
            "participants": [
                {
                    "vehicle_index": 0,
                    "is_human": True,
                    "steam_name": "Report Driver",
                    "driver_id": 1,
                    "team_id": 2,
                    "grid_position": 1,
                    "position": 1,
                    "result_status": 3,
                    "total_race_time": 5000.1,
                    "best_lap_ms": 88000,
                    "penalties_time": 0,
                    "num_penalties": 0,
                    "num_pit_stops": 1,
                    "tyre_stints": [],
                    "has_fastest_lap": True,
                }
            ],
            "events": [],
        }

    @staticmethod
    def _telemetry_entry(session_uid: int, *, race_id: int | None) -> dict:
        snapshot = TelemetrySnapshot(
            laps={
                0: {
                    1: {
                        "lap_time_ms": 88_123,
                        "samples": [{"t": 1.0, "x": 10.0, "z": 20.0, "spd": 250}],
                    }
                }
            },
            session_history={
                0: {
                    "vehicle_index": 0,
                    "best_lap_num": 1,
                    "best_s1_lap": 1,
                    "best_s2_lap": 1,
                    "best_s3_lap": 1,
                    "laps": [
                        {
                            "lap_number": 1,
                            "lap_time_ms": 88_123,
                            "sector1_ms": 29_000,
                            "sector2_ms": 29_000,
                            "sector3_ms": 30_123,
                            "lap_valid": True,
                        }
                    ],
                }
            },
        ).to_payload()
        return {
            "cache_version": 1,
            "session_uid": session_uid,
            "race_id": race_id,
            "saved_at": "2026-03-27T12:00:00+00:00",
            "updated_at": "2026-03-27T12:05:00+00:00",
            "last_attempt_at": "2026-03-27T12:05:00+00:00",
            "attempt_count": 2,
            "last_error": "HTTP 503" if race_id else None,
            "last_http_status": 503 if race_id else None,
            "last_outcome": "failed" if race_id else "pending",
            "snapshot": snapshot,
        }

    def test_report_classifies_race_upload_backlog_with_replayable_raw_log(self) -> None:
        session_uid = 700001
        race_cache_path = self.data_dir / "final_classification_cache.json"
        race_cache_path.write_text(
            json.dumps([{"payload": self._race_payload(session_uid), "session_uid": session_uid}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_sample_raw_log(self.data_dir / "raw_logs" / "session_fixture.bin", session_uid=session_uid)

        report = build_postmortem_report(data_dir=self.data_dir, max_raw_logs=5, analyze_raw_logs=True)

        self.assertEqual(report["summary"]["pending_race_uploads"], 1)
        self.assertEqual(report["summary"]["issue_count"], 1)
        self.assertEqual(report["sessions"][0]["status"], "race_upload_pending")
        self.assertIn("retry cached delivery", report["sessions"][0]["recommended_action"])
        self.assertTrue(report["sessions"][0]["raw_log"]["replay_command"].endswith("--agent"))

    def test_report_flags_ready_and_orphaned_telemetry(self) -> None:
        telemetry_cache_path = self.data_dir / "telemetry_flush_cache.json"
        telemetry_cache_path.write_text(
            json.dumps(
                [
                    self._telemetry_entry(800001, race_id=55),
                    self._telemetry_entry(800002, race_id=None),
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        report = build_postmortem_report(data_dir=self.data_dir, max_raw_logs=5, analyze_raw_logs=True)

        self.assertEqual(report["summary"]["pending_telemetry"], 2)
        self.assertEqual(report["summary"]["pending_telemetry_ready_to_flush"], 1)
        self.assertEqual(report["summary"]["pending_telemetry_waiting_for_race_id"], 1)

        statuses = {session["session_uid"]: session["status"] for session in report["sessions"]}
        self.assertEqual(statuses[800001], "telemetry_flush_pending")
        self.assertEqual(statuses[800002], "orphaned_telemetry")
        self.assertIn("quarantine-orphaned-telemetry", report["commands"]["quarantine_orphans"])

    def test_quarantine_orphaned_telemetry_archives_irrecoverable_entries(self) -> None:
        telemetry_cache_path = self.data_dir / "telemetry_flush_cache.json"
        telemetry_cache_path.write_text(
            json.dumps(
                [
                    self._telemetry_entry(800001, race_id=55),
                    self._telemetry_entry(800002, race_id=None),
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        report = build_postmortem_report(data_dir=self.data_dir, max_raw_logs=5, analyze_raw_logs=True)
        archived = quarantine_orphaned_telemetry(report, data_dir=self.data_dir)

        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["session_uid"], 800002)

        refreshed = build_postmortem_report(data_dir=self.data_dir, max_raw_logs=5, analyze_raw_logs=True)
        statuses = {session["session_uid"]: session["status"] for session in refreshed["sessions"]}
        self.assertEqual(statuses[800001], "telemetry_flush_pending")
        self.assertNotIn(800002, statuses)

        archive_file = self.data_dir / "telemetry_orphan_archive.json"
        archive_payload = json.loads(archive_file.read_text(encoding="utf-8"))
        self.assertEqual(len(archive_payload), 1)
        self.assertEqual(archive_payload[0]["session_uid"], 800002)


if __name__ == "__main__":
    unittest.main()
