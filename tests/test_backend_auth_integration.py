from __future__ import annotations

import uuid

from tests.backend_integration_support import BackendIntegrationCase


class BackendAuthIntegrationTests(BackendIntegrationCase):
    def _create_host_season(self, token: str) -> tuple[int, int]:
        lobby_response = self.client.post(
            "/api/lobby",
            json={"name": f"Host Lobby {uuid.uuid4().hex[:6]}", "description": "integration"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(lobby_response.status_code, 200, lobby_response.text)
        lobby = lobby_response.json()

        season_response = self.client.post(
            f"/api/lobby/{lobby['id']}/seasons",
            json={"name": f"Season {uuid.uuid4().hex[:6]}"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(season_response.status_code, 200, season_response.text)
        season = season_response.json()
        return lobby["id"], season["id"]

    def _race_payload(self, season_id: int) -> dict:
        return {
            "season_id": season_id,
            "session_uid": 700000 + int(uuid.uuid4().hex[:6], 16),
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
                    "steam_name": "Auth Driver",
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
                    "tyre_stints": [{"compound": "Soft", "laps": 5}],
                    "has_fastest_lap": True,
                }
            ],
            "events": [{"event_code": "FTLP", "event_data": {"vehicleIdx": 0}}],
        }

    def test_web_and_launcher_tokens_authorize_real_lobby_paths(self) -> None:
        user = self.register_user("auth-host")
        token = user["token"]

        me_response = self.client.get("/api/web/me/by-token", headers=self.auth_headers(token))
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["email"], user["email"])

        launcher_login = self.client.post(
            "/api/web/launcher/login",
            json={"email": user["email"], "password": "Password123!"},
        )
        self.assertEqual(launcher_login.status_code, 200, launcher_login.text)
        launcher_token = launcher_login.json()["token"]

        host_seasons_unauthorized = self.client.get("/api/lobby/host-seasons")
        self.assertEqual(host_seasons_unauthorized.status_code, 401, host_seasons_unauthorized.text)

        _, season_id = self._create_host_season(launcher_token)
        host_seasons = self.client.get("/api/lobby/host-seasons", headers=self.auth_headers(launcher_token))
        self.assertEqual(host_seasons.status_code, 200, host_seasons.text)
        self.assertEqual([item["id"] for item in host_seasons.json()], [season_id])

    def test_agent_token_is_enforced_for_race_and_telemetry_submit(self) -> None:
        user = self.register_user("agent-auth-host")
        _, season_id = self._create_host_season(user["token"])

        race_response = self.client.post("/api/race/submit", json=self._race_payload(season_id))
        self.assertEqual(race_response.status_code, 401, race_response.text)

        race_response = self.client.post(
            "/api/race/submit",
            json=self._race_payload(season_id),
            headers=self.agent_headers(),
        )
        self.assertEqual(race_response.status_code, 200, race_response.text)
        race_id = race_response.json()["race_id"]

        telemetry_payload = {
            "race_id": race_id,
            "vehicle_index": 0,
            "lap_number": 1,
            "samples": [
                {
                    "t": 1.0,
                    "x": 0.0,
                    "z": 0.0,
                    "spd": 250,
                    "thr": 1.0,
                    "brk": 0.0,
                    "gear": 8,
                    "drs": 1,
                    "dist": 100.0,
                    "str": 0.1,
                }
            ],
        }

        telemetry_response = self.client.post("/api/telemetry/submit", json=telemetry_payload)
        self.assertEqual(telemetry_response.status_code, 401, telemetry_response.text)

        telemetry_response = self.client.post(
            "/api/telemetry/submit",
            json=telemetry_payload,
            headers=self.agent_headers(),
        )
        self.assertEqual(telemetry_response.status_code, 200, telemetry_response.text)
