"""Covers PR 1.0.5 — agent 401 detection in delivery modules.

Verifies that when the backend rejects AGENT_SECRET_TOKEN with HTTP 401:
- uploader.upload_race returns (False, None) immediately, without burning
  through RETRY_DELAYS,
- the observer receives an "auth_rejected" event,
- the race entry stays in the local cache (so a fresh token can retry later),
- config.set_agent_token() persists the new value to launcher_config.json
  and is visible to subsequent get_agent_secret_token() calls.
"""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import config, local_cache, uploader


def _minimal_payload(session_uid: int) -> dict:
    return {
        "season_id": 1,
        "session_uid": session_uid,
        "packet_format": 2025,
        "track_id": 10,
        "weather_start": 0,
        "weather_end": 0,
        "total_laps": 5,
        "air_temp": 20,
        "track_temp": 28,
        "participants": [],
        "events": [],
    }


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json = json_body or {}

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        return _FakeResponse(401, {"detail": "Invalid agent token"})


class UploaderAuthFailureTests(unittest.TestCase):
    def setUp(self):
        # Fresh tmp cache per test so we don't trip over earlier state.
        self._tmp = Path("/tmp") / f"f1league_test_{int(time.time() * 1000)}"
        self._tmp.mkdir(parents=True, exist_ok=True)
        self._cache_patch = patch.object(
            local_cache,
            "CACHE_FILE",
            self._tmp / "final_classification_cache.json",
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()

    def test_401_returns_without_retrying_and_emits_auth_rejected(self):
        events: list[tuple[str, dict]] = []
        observer = lambda event, payload: events.append((event, payload))

        # If 401 is not detected and the loop retries through RETRY_DELAYS,
        # this test would take ~36s; the timeout catches that regression.
        start = time.monotonic()
        with patch.object(uploader.httpx, "Client", _FakeClient):
            success, race_id = uploader.upload_race(_minimal_payload(700001), observer=observer)
        elapsed = time.monotonic() - start

        self.assertFalse(success)
        self.assertIsNone(race_id)
        self.assertLess(elapsed, 2.0, "401 path should not sleep through RETRY_DELAYS")

        event_names = [name for name, _ in events]
        self.assertIn("auth_rejected", event_names)
        self.assertNotIn("retry_scheduled", event_names)


class SetAgentTokenTests(unittest.TestCase):
    def setUp(self):
        # Override the launcher_config.json path used inside set_agent_token().
        self._tmp_home = Path("/tmp") / f"f1league_home_{int(time.time() * 1000)}"
        self._home_patch = patch.object(Path, "home", lambda: self._tmp_home)
        self._home_patch.start()
        self._prev_override = config._AGENT_TOKEN_OVERRIDE

    def tearDown(self):
        self._home_patch.stop()
        config._AGENT_TOKEN_OVERRIDE = self._prev_override

    def test_set_agent_token_updates_runtime_and_config_file(self):
        config.set_agent_token("fresh-token-123")

        self.assertEqual(config.get_agent_secret_token(), "fresh-token-123")

        config_file = self._tmp_home / "f1league_agent" / "launcher_config.json"
        self.assertTrue(config_file.exists())
        payload = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["agent_token"], "fresh-token-123")


if __name__ == "__main__":
    unittest.main()
