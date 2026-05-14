from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import local_cache, uploader


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


class UploadCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="f1t_upload_cache_")
        self.addCleanup(self._tmp_dir.cleanup)

        cache_file = Path(self._tmp_dir.name) / "final_classification_cache.json"
        self._cache_patch = mock.patch.multiple(
            local_cache,
            CACHE_FILE=cache_file,
            CACHE_BACKUP_FILE=cache_file.with_suffix(".json.bak"),
            CACHE_TEMP_FILE=cache_file.with_suffix(".json.tmp"),
        )
        self._cache_patch.start()
        self.addCleanup(self._cache_patch.stop)

    @staticmethod
    def _payload(session_uid: int = 555) -> dict:
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
                    "best_lap_ms": 88_111,
                    "penalties_time": 0,
                    "num_penalties": 0,
                    "num_pit_stops": 1,
                    "tyre_stints": [{"compound": "Soft", "laps": 12}],
                    "has_fastest_lap": True,
                }
            ],
            "events": [{"event_code": "FTLP", "event_data": {"vehicleIdx": 0}}],
        }

    def test_cache_normalizes_legacy_entry_and_tracks_retry_metadata(self):
        legacy_payload = self._payload(session_uid=111)
        cache_path = local_cache.CACHE_FILE
        cache_path.write_text(
            json.dumps([{"saved_at": "2026-03-27T00:00:00+00:00", **legacy_payload}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        entries = local_cache.load_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["payload"]["session_uid"], 111)
        self.assertEqual(entries[0]["saved_at"], "2026-03-27T00:00:00+00:00")
        self.assertEqual(entries[0]["attempt_count"], 0)

        attempt_entry = local_cache.mark_attempt(111)
        self.assertIsNotNone(attempt_entry)
        failed_entry = local_cache.mark_failure(111, "HTTP 503", http_status=503)
        self.assertIsNotNone(failed_entry)

        updated = local_cache.load_all()[0]
        self.assertEqual(updated["attempt_count"], 1)
        self.assertEqual(updated["last_outcome"], "failed")
        self.assertEqual(updated["last_http_status"], 503)
        self.assertEqual(updated["last_error"], "HTTP 503")

    def test_upload_race_treats_duplicate_response_as_success_and_clears_cache(self):
        payload = self._payload(session_uid=222)
        responses = [_FakeResponse(200, {"status": "duplicate", "race_id": 77, "round": 5})]
        captured_posts: list[dict] = []

        with mock.patch("agent.uploader.RETRY_DELAYS", []):
            with mock.patch.object(uploader, "AGENT_SECRET_TOKEN", "agent-secret"):
                with mock.patch(
                    "agent.uploader.httpx.Client",
                    side_effect=lambda *args, **kwargs: _FakeClient(responses, captured_posts),
                ):
                    success, race_id = uploader.upload_race(payload)

        self.assertTrue(success)
        self.assertEqual(race_id, 77)
        self.assertEqual(local_cache.load_all(), [])
        self.assertEqual(len(captured_posts), 1)
        self.assertEqual(captured_posts[0]["json"], payload)
        self.assertEqual(captured_posts[0]["headers"].get("X-Agent-Token"), "agent-secret")

    def test_retry_pending_uploads_reuses_cached_entry_after_restart(self):
        payload = self._payload(session_uid=333)
        local_cache.save(payload)
        local_cache.mark_attempt(333)
        local_cache.mark_failure(333, "backend timeout")

        responses = [_FakeResponse(200, {"status": "ok", "race_id": 88, "round": 6})]
        captured_posts: list[dict] = []
        observed: list[tuple[str, dict]] = []

        with mock.patch("agent.uploader.RETRY_DELAYS", []):
            with mock.patch(
                "agent.uploader.httpx.Client",
                side_effect=lambda *args, **kwargs: _FakeClient(responses, captured_posts),
            ):
                asyncio.run(
                    uploader.retry_pending_uploads(
                        observer=lambda event, payload=None: observed.append((event, payload or {}))
                    )
                )

        self.assertEqual(local_cache.load_all(), [])
        self.assertEqual(len(captured_posts), 1)
        retrying_events = [payload for event, payload in observed if event == "retrying_cached"]
        self.assertEqual(len(retrying_events), 1)
        self.assertEqual(retrying_events[0]["session_uid"], 333)
        self.assertEqual(retrying_events[0]["attempt_count"], 1)
        self.assertEqual(retrying_events[0]["last_error"], "backend timeout")


if __name__ == "__main__":
    unittest.main()
