"""PR 1.2 — AGENT_SECRET_TOKEN fail-closed behavior.

Before PR 1.2 verify_agent_token silently allowed every request when
the env var was unset (back-compat shim from initial rollout). After:
- no env var → 503 with explicit message,
- no header   → 401,
- wrong header → 401 (constant-time compare),
- correct header → 200/2xx via the original endpoint.
"""
from __future__ import annotations

import os
import uuid
from unittest import mock

from tests.backend_integration_support import BackendIntegrationCase


def _race_submit_payload() -> dict:
    return {
        "season_id": 1,
        "session_uid": 800000 + int(uuid.uuid4().hex[:6], 16),
        "packet_format": 2025,
        "track_id": 10,
        "weather_start": 0,
        "weather_end": 0,
        "total_laps": 5,
        "air_temp": 24,
        "track_temp": 31,
        "participants": [],
        "events": [],
    }


class AgentTokenFailClosedTests(BackendIntegrationCase):
    def test_503_when_server_has_no_agent_secret_configured(self):
        with mock.patch.dict(os.environ, {"AGENT_SECRET_TOKEN": ""}, clear=False):
            response = self.client.post("/api/race/submit", json=_race_submit_payload())
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("AGENT_SECRET_TOKEN", response.text)

    def test_401_when_header_missing(self):
        # Harness already sets AGENT_SECRET_TOKEN=integration-agent-secret.
        response = self.client.post("/api/race/submit", json=_race_submit_payload())
        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn("Missing", response.text)

    def test_401_when_header_wrong(self):
        response = self.client.post(
            "/api/race/submit",
            json=_race_submit_payload(),
            headers={"X-Agent-Token": "definitely-not-the-real-token"},
        )
        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn("Invalid", response.text)
