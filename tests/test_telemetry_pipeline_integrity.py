from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import local_cache, telemetry_delivery, uploader
from agent.telemetry_buffer import TelemetryBuffer, TelemetrySnapshot
from backend.models.models import LapTelemetry, RaceResult, RaceSessionHistory
from backend.routers.telemetry import compare_laps, get_best_lap, submit_session_history, submit_telemetry
from backend.routers.telemetry import LapSubmit, SessionHistoryLap, SessionHistorySubmit, TelemetrySample, VehicleHistory


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[object], captured_posts: list[dict]):
        self._responses = responses
        self._captured_posts = captured_posts

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def post(self, url: str, json: dict, headers: dict | None = None) -> _FakeResponse:
        self._captured_posts.append({"url": url, "json": json, "headers": headers or {}})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def get(self, url: str, headers: dict | None = None) -> _FakeResponse:
        self._captured_posts.append({"url": url, "json": None, "headers": headers or {}})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeScalarResult:
    def __init__(self, first_value=None, all_values=None):
        self._first_value = first_value
        self._all_values = list(all_values or ([] if first_value is None else [first_value]))

    def scalars(self) -> "_FakeScalarResult":
        return self

    def first(self):
        return self._first_value

    def all(self):
        return list(self._all_values)


class _FakeAsyncSession:
    def __init__(self, execute_results: list[_FakeScalarResult], *, commit_exc: Exception | None = None):
        self._execute_results = list(execute_results)
        self._commit_exc = commit_exc
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    async def execute(self, query):
        if not self._execute_results:
            raise AssertionError("Unexpected execute() call")
        return self._execute_results.pop(0)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_calls += 1
        if self._commit_exc is not None:
            raise self._commit_exc

    async def rollback(self) -> None:
        self.rollback_calls += 1


class TelemetryBufferIntegrityTests(unittest.TestCase):
    def test_snapshot_keeps_completed_lap_time_and_backfills_final_lap_from_history(self):
        buffer = TelemetryBuffer()
        buffer._buffers = {
            0: {
                1: {"lap_time_ms": None, "samples": [{"t": 10.0, "x": 1.0, "z": 2.0}]},
                2: {"lap_time_ms": None, "samples": [{"t": 20.0, "x": 3.0, "z": 4.0}]},
            }
        }

        buffer.update_lap(0, lap_number=2, lap_distance=1200.0, session_time=90.0, last_lap_ms=88_123)
        buffer.update_session_history(
            0,
            {
                "vehicle_index": 0,
                "best_lap_num": 2,
                "laps": [
                    {"lap_number": 1, "lap_time_ms": 88_123, "sector1_ms": 29_000, "sector2_ms": 29_000, "sector3_ms": 30_123, "lap_valid": True},
                    {"lap_number": 2, "lap_time_ms": 89_456, "sector1_ms": 29_500, "sector2_ms": 29_800, "sector3_ms": 30_156, "lap_valid": True},
                ],
            },
        )

        snapshot = buffer.stop_and_snapshot()

        self.assertEqual(snapshot.laps[0][1]["lap_time_ms"], 88_123)
        self.assertEqual(snapshot.laps[0][2]["lap_time_ms"], 89_456)
        self.assertEqual(snapshot.session_history[0]["best_lap_num"], 2)


class TelemetryDeliveryPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="f1t_telemetry_integrity_")
        self.addCleanup(self._tmp_dir.cleanup)

        race_cache_file = Path(self._tmp_dir.name) / "final_classification_cache.json"
        telemetry_cache_file = Path(self._tmp_dir.name) / "telemetry_flush_cache.json"

        self._race_cache_patch = mock.patch.multiple(
            local_cache,
            CACHE_FILE=race_cache_file,
            CACHE_BACKUP_FILE=race_cache_file.with_suffix(".json.bak"),
            CACHE_TEMP_FILE=race_cache_file.with_suffix(".json.tmp"),
        )
        self._telemetry_cache_patch = mock.patch.multiple(
            telemetry_delivery,
            TELEMETRY_CACHE_FILE=telemetry_cache_file,
            CACHE_BACKUP_FILE=telemetry_cache_file.with_suffix(".json.bak"),
            CACHE_TEMP_FILE=telemetry_cache_file.with_suffix(".json.tmp"),
        )
        self._race_cache_patch.start()
        self._telemetry_cache_patch.start()
        self.addCleanup(self._race_cache_patch.stop)
        self.addCleanup(self._telemetry_cache_patch.stop)

    @staticmethod
    def _race_payload(session_uid: int = 444) -> dict:
        return {
            "season_id": 1,
            "session_uid": session_uid,
            "packet_format": 2025,
            "track_id": 10,
            "weather_start": 0,
            "weather_end": 1,
            "total_laps": 58,
            "air_temp": 24,
            "track_temp": 31,
            "participants": [
                {
                    "vehicle_index": 0,
                    "is_human": True,
                    "steam_name": "Driver One",
                    "driver_id": 1,
                    "team_id": 2,
                    "grid_position": 1,
                    "position": 1,
                    "result_status": 3,
                    "total_race_time": 5000.5,
                    "best_lap_ms": 88_123,
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
    def _snapshot() -> TelemetrySnapshot:
        return TelemetrySnapshot(
            laps={
                0: {
                    1: {
                        "lap_time_ms": 88_123,
                        "samples": [{"t": 1.0, "x": 10.0, "z": 20.0, "spd": 250, "thr": 1.0, "brk": 0.0, "gear": 8, "drs": 1, "dist": 100.0}],
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
                    "laps": [{"lap_number": 1, "lap_time_ms": 88_123, "sector1_ms": 29_000, "sector2_ms": 29_000, "sector3_ms": 30_123, "lap_valid": True}],
                }
            },
        )

    def test_race_upload_success_attaches_race_id_for_cached_telemetry_retry(self):
        telemetry_delivery.save_snapshot(444, self._snapshot())

        race_posts: list[dict] = []
        race_responses = [_FakeResponse(200, {"status": "ok", "race_id": 77, "round": 5})]
        with mock.patch("agent.uploader.RETRY_DELAYS", []):
            with mock.patch(
                "agent.uploader.httpx.Client",
                side_effect=lambda *args, **kwargs: _FakeClient(race_responses, race_posts),
            ):
                success, race_id = uploader.upload_race(self._race_payload())

        self.assertTrue(success)
        self.assertEqual(race_id, 77)
        pending_entry = telemetry_delivery.load_all()[0]
        self.assertEqual(pending_entry["race_id"], 77)
        self.assertEqual(local_cache.load_all(), [])

        telemetry_posts: list[dict] = []
        telemetry_responses = [
            _FakeResponse(200, {"status": "ok", "vehicles_stored": 1}),
            _FakeResponse(200, {"status": "ok", "samples": 1}),
        ]
        with mock.patch("agent.telemetry_delivery.RETRY_DELAYS", []):
            with mock.patch.object(telemetry_delivery, "AGENT_SECRET_TOKEN", "agent-secret"):
                with mock.patch(
                    "agent.telemetry_delivery.httpx.Client",
                    side_effect=lambda *args, **kwargs: _FakeClient(telemetry_responses, telemetry_posts),
                ):
                    asyncio.run(telemetry_delivery.retry_pending())

        self.assertEqual(telemetry_delivery.load_all(), [])
        self.assertEqual(len(telemetry_posts), 2)
        self.assertEqual(telemetry_posts[0]["url"].split("/")[-1], "session-history")
        self.assertEqual(telemetry_posts[1]["url"].split("/")[-1], "submit")
        self.assertEqual(telemetry_posts[1]["json"]["race_id"], 77)
        self.assertEqual(telemetry_posts[1]["json"]["lap_time_ms"], 88_123)
        self.assertEqual(telemetry_posts[0]["headers"].get("X-Agent-Token"), "agent-secret")
        self.assertEqual(telemetry_posts[1]["headers"].get("X-Agent-Token"), "agent-secret")

    def test_retry_pending_resolves_missing_race_id_from_backend_before_flush(self):
        telemetry_delivery.save_snapshot(444, self._snapshot())

        telemetry_posts: list[dict] = []
        telemetry_responses = [
            _FakeResponse(200, {"status": "ok", "race_id": 91}),
            _FakeResponse(200, {"status": "ok", "vehicles_stored": 1}),
            _FakeResponse(200, {"status": "ok", "samples": 1}),
        ]
        with mock.patch("agent.telemetry_delivery.RETRY_DELAYS", []):
            with mock.patch.object(telemetry_delivery, "AGENT_SECRET_TOKEN", "agent-secret"):
                with mock.patch(
                    "agent.telemetry_delivery.httpx.Client",
                    side_effect=lambda *args, **kwargs: _FakeClient(telemetry_responses, telemetry_posts),
                ):
                    asyncio.run(telemetry_delivery.retry_pending())

        self.assertEqual(telemetry_delivery.load_all(), [])
        self.assertTrue(telemetry_posts[0]["url"].endswith("/api/race/session/444"))
        self.assertIsNone(telemetry_posts[0]["json"])
        self.assertEqual(telemetry_posts[0]["headers"].get("X-Agent-Token"), "agent-secret")
        self.assertEqual(telemetry_posts[1]["json"]["race_id"], 91)
        self.assertEqual(telemetry_posts[2]["json"]["race_id"], 91)


class TelemetryRouterIntegrityTests(unittest.TestCase):
    def test_submit_telemetry_updates_existing_lap_with_history_backfill(self):
        existing_lap = LapTelemetry(
            race_id=1,
            vehicle_index=0,
            lap_number=1,
            lap_time_ms=None,
            samples=[{"t": 0.0}],
        )
        history_row = RaceSessionHistory(
            race_id=1,
            vehicle_index=0,
            best_lap_num=1,
            laps=[{"lap_number": 1, "lap_time_ms": 88_000, "sector1_ms": 29_000, "sector2_ms": 29_000, "sector3_ms": 30_000, "lap_valid": True}],
        )
        db = _FakeAsyncSession(
            [
                _FakeScalarResult(history_row),
                _FakeScalarResult(existing_lap),
            ]
        )

        payload = LapSubmit(
            race_id=1,
            vehicle_index=0,
            lap_number=1,
            lap_time_ms=None,
            samples=[TelemetrySample(t=1.0, x=0.0, z=0.0, spd=250, thr=1.0, brk=0.0, gear=8, drs=1, dist=100.0)],
        )

        result = asyncio.run(submit_telemetry(payload, db=db, _=True))

        self.assertEqual(result["status"], "updated")
        self.assertEqual(existing_lap.lap_time_ms, 88_000)
        self.assertEqual(db.commit_calls, 1)

    def test_submit_session_history_merges_existing_row_and_backfills_saved_laps(self):
        existing_history = RaceSessionHistory(
            race_id=1,
            vehicle_index=0,
            best_lap_num=0,
            best_s1_lap=0,
            best_s2_lap=0,
            best_s3_lap=0,
            laps=[{"lap_number": 1, "lap_time_ms": 88_500, "sector1_ms": 29_100, "sector2_ms": 29_300, "sector3_ms": 30_100, "lap_valid": True}],
        )
        existing_lap = LapTelemetry(
            race_id=1,
            vehicle_index=0,
            lap_number=2,
            lap_time_ms=None,
            samples=[{"t": 0.0}],
        )
        db = _FakeAsyncSession(
            [
                _FakeScalarResult(existing_history),
                _FakeScalarResult(all_values=[existing_lap]),
            ]
        )

        payload = SessionHistorySubmit(
            race_id=1,
            vehicles=[
                VehicleHistory(
                    vehicle_index=0,
                    best_lap_num=2,
                    best_s1_lap=2,
                    best_s2_lap=2,
                    best_s3_lap=2,
                    laps=[
                        SessionHistoryLap(lap_number=1, lap_time_ms=88_500, sector1_ms=29_100, sector2_ms=29_300, sector3_ms=30_100, lap_valid=True),
                        SessionHistoryLap(lap_number=2, lap_time_ms=88_000, sector1_ms=28_900, sector2_ms=29_000, sector3_ms=30_100, lap_valid=True),
                    ],
                )
            ],
        )

        result = asyncio.run(submit_session_history(payload, db=db, _=True))

        self.assertEqual(result["vehicles_updated"], 1)
        self.assertEqual(result["laps_backfilled"], 1)
        self.assertEqual(existing_history.best_lap_num, 2)
        self.assertEqual(len(existing_history.laps), 2)
        self.assertEqual(existing_lap.lap_time_ms, 88_000)

    def test_get_best_lap_prefers_history_time_for_legacy_null_rows(self):
        history_row = RaceSessionHistory(
            race_id=1,
            vehicle_index=0,
            best_lap_num=1,
            laps=[
                {"lap_number": 1, "lap_time_ms": 88_000, "sector1_ms": 29_000, "sector2_ms": 29_000, "sector3_ms": 30_000, "lap_valid": True},
                {"lap_number": 2, "lap_time_ms": 89_500, "sector1_ms": 29_500, "sector2_ms": 29_900, "sector3_ms": 30_100, "lap_valid": True},
            ],
        )
        lap_one = LapTelemetry(race_id=1, vehicle_index=0, lap_number=1, lap_time_ms=None, samples=[{"t": 1.0}])
        lap_two = LapTelemetry(race_id=1, vehicle_index=0, lap_number=2, lap_time_ms=89_500, samples=[{"t": 2.0}])
        db = _FakeAsyncSession(
            [
                _FakeScalarResult(history_row),
                _FakeScalarResult(all_values=[lap_one, lap_two]),
            ]
        )

        result = asyncio.run(get_best_lap(1, 0, db=db))

        self.assertEqual(result["lap_number"], 1)
        self.assertEqual(result["lap_time_ms"], 88_000)

    def test_compare_laps_uses_effective_lap_times_and_driver_metadata(self):
        history_a = RaceSessionHistory(
            race_id=1,
            vehicle_index=0,
            best_lap_num=1,
            laps=[{"lap_number": 1, "lap_time_ms": 88_000, "sector1_ms": 29_000, "sector2_ms": 29_000, "sector3_ms": 30_000, "lap_valid": True}],
        )
        history_b = RaceSessionHistory(
            race_id=1,
            vehicle_index=1,
            best_lap_num=2,
            laps=[{"lap_number": 2, "lap_time_ms": 89_100, "sector1_ms": 29_300, "sector2_ms": 29_600, "sector3_ms": 30_200, "lap_valid": True}],
        )
        lap_a = LapTelemetry(race_id=1, vehicle_index=0, lap_number=1, lap_time_ms=None, samples=[{"t": 1.0}])
        lap_b = LapTelemetry(race_id=1, vehicle_index=1, lap_number=2, lap_time_ms=89_100, samples=[{"t": 2.0}])
        results = [
            RaceResult(race_id=1, vehicle_index=0, driver_id=1, driver_name="Alice", team_id=2, team_name="Team A", is_human=True),
            RaceResult(race_id=1, vehicle_index=1, driver_id=2, driver_name="Bob", team_id=3, team_name="Team B", is_human=True),
        ]
        db = _FakeAsyncSession(
            [
                _FakeScalarResult(history_a),
                _FakeScalarResult(history_b),
                _FakeScalarResult(all_values=[lap_a]),
                _FakeScalarResult(all_values=[lap_b]),
                _FakeScalarResult(all_values=results),
            ]
        )

        result = asyncio.run(compare_laps(1, a=0, b=1, db=db))

        self.assertEqual(result["a"]["lap_time_ms"], 88_000)
        self.assertEqual(result["a"]["driver_name"], "Alice")
        self.assertEqual(result["b"]["lap_time_ms"], 89_100)
        self.assertEqual(result["b"]["driver_name"], "Bob")


if __name__ == "__main__":
    unittest.main()
