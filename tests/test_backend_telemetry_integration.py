from __future__ import annotations

import os
import uuid
from unittest import mock

from tests.backend_integration_support import BackendIntegrationCase


def _steam_id64() -> str:
    return str(76561190000000000 + int(uuid.uuid4().hex[:6], 16))


class BackendTelemetryIntegrationTests(BackendIntegrationCase):
    def _insert_player(self, name: str, steam_name: str, *, telegram_id: int | None = None) -> int:
        async def create_player(session):
            from backend.models.models import Player

            player = Player(
                name=name,
                steam_id64=_steam_id64(),
                steam_names=[steam_name],
                telegram_id=telegram_id,
            )
            session.add(player)
            await session.commit()
            await session.refresh(player)
            return player.id

        return self.harness.db_call(create_player)

    def _create_lobby_and_season(self, token: str) -> tuple[int, int]:
        lobby_response = self.client.post(
            "/api/lobby",
            json={"name": f"Telemetry Lobby {uuid.uuid4().hex[:6]}", "description": "telemetry"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(lobby_response.status_code, 200, lobby_response.text)
        lobby = lobby_response.json()

        season_response = self.client.post(
            f"/api/lobby/{lobby['id']}/seasons",
            json={"name": f"Telemetry Season {uuid.uuid4().hex[:6]}"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(season_response.status_code, 200, season_response.text)
        season = season_response.json()
        return lobby["id"], season["id"]

    def _lap_samples(self, *, distance_shift: float, slower: bool) -> list[dict]:
        return [
            {"t": 0.0, "x": 0.0, "z": 0.0, "spd": 312 if not slower else 305, "thr": 1.0, "brk": 0.0, "gear": 8, "drs": 1, "dist": 0.0 + distance_shift, "str": 0.02},
            {"t": 0.2, "x": 1.0, "z": 0.0, "spd": 305 if not slower else 298, "thr": 1.0, "brk": 0.0, "gear": 8, "drs": 1, "dist": 80.0 + distance_shift, "str": 0.01},
            {"t": 0.4, "x": 2.0, "z": 0.0, "spd": 260 if not slower else 250, "thr": 0.3, "brk": 0.2, "gear": 6, "drs": 0, "dist": 120.0 + distance_shift, "str": -0.08},
            {"t": 0.6, "x": 3.0, "z": 0.0, "spd": 190 if not slower else 180, "thr": 0.1, "brk": 0.7, "gear": 4, "drs": 0, "dist": 150.0 + distance_shift, "str": -0.18},
            {"t": 0.8, "x": 4.0, "z": 0.0, "spd": 142 if not slower else 135, "thr": 0.2, "brk": 0.9, "gear": 3, "drs": 0, "dist": 170.0 + distance_shift, "str": -0.24},
            {"t": 1.0, "x": 5.0, "z": 0.0, "spd": 150 if not slower else 145, "thr": 0.45, "brk": 0.25, "gear": 3, "drs": 0, "dist": 192.0 + distance_shift, "str": -0.12},
            {"t": 1.2, "x": 6.0, "z": 0.0, "spd": 205 if not slower else 198, "thr": 0.82, "brk": 0.0, "gear": 5, "drs": 0, "dist": 235.0 + distance_shift, "str": 0.06},
            {"t": 1.4, "x": 7.0, "z": 0.0, "spd": 268 if not slower else 258, "thr": 1.0, "brk": 0.0, "gear": 7, "drs": 1, "dist": 290.0 + distance_shift, "str": 0.04},
        ]

    def _seed_analysis_race(self) -> dict:
        owner = self.register_user("telemetry-owner")
        hero_name = f"Telemetry Hero {uuid.uuid4().hex[:4]}"
        rival_name = f"Telemetry Rival {uuid.uuid4().hex[:4]}"
        hero_player_id = self._insert_player(
            "Hero Player",
            hero_name,
            telegram_id=100000 + int(uuid.uuid4().hex[:6], 16),
        )
        self._insert_player("Rival Player", rival_name)

        link_response = self.client.post(
            "/api/web/link-player",
            json={"player_id": hero_player_id},
            headers=self.auth_headers(owner["token"]),
        )
        self.assertEqual(link_response.status_code, 200, link_response.text)

        _, season_id = self._create_lobby_and_season(owner["token"])

        race_payload = {
            "season_id": season_id,
            "session_uid": 810000 + int(uuid.uuid4().hex[:6], 16),
            "packet_format": 2025,
            "track_id": 10,
            "weather_start": 0,
            "weather_end": 3,
            "total_laps": 2,
            "air_temp": 25,
            "track_temp": 32,
            "participants": [
                {
                    "vehicle_index": 0,
                    "is_human": True,
                    "steam_name": hero_name,
                    "driver_id": 1,
                    "team_id": 2,
                    "grid_position": 2,
                    "position": 1,
                    "result_status": 3,
                    "total_race_time": 5000.2,
                    "best_lap_ms": 88000,
                    "penalties_time": 0,
                    "num_penalties": 0,
                    "num_pit_stops": 1,
                    "tyre_stints": [{"compound": "Soft", "laps": 2}],
                    "has_fastest_lap": True,
                },
                {
                    "vehicle_index": 1,
                    "is_human": True,
                    "steam_name": rival_name,
                    "driver_id": 11,
                    "team_id": 1,
                    "grid_position": 1,
                    "position": 2,
                    "result_status": 3,
                    "total_race_time": 5003.7,
                    "best_lap_ms": 88500,
                    "penalties_time": 0,
                    "num_penalties": 0,
                    "num_pit_stops": 1,
                    "tyre_stints": [{"compound": "Medium", "laps": 2}],
                    "has_fastest_lap": False,
                },
            ],
            "events": [{"event_code": "FTLP", "event_data": {"vehicleIdx": 0}}],
        }

        with mock.patch("backend.routers.races.recalc_standings", new=mock.AsyncMock()):
            with mock.patch("backend.routers.races._update_ratings", new=mock.AsyncMock()):
                with mock.patch("backend.routers.races.notify_race_uploaded", new=mock.AsyncMock()):
                    race_response = self.client.post(
                        "/api/race/submit",
                        json=race_payload,
                        headers=self.agent_headers(),
                    )
        self.assertEqual(race_response.status_code, 200, race_response.text)
        race_id = race_response.json()["race_id"]

        history_payload = {
            "race_id": race_id,
            "vehicles": [
                {
                    "vehicle_index": 0,
                    "best_lap_num": 2,
                    "best_s1_lap": 2,
                    "best_s2_lap": 2,
                    "best_s3_lap": 2,
                    "laps": [
                        {"lap_number": 1, "lap_time_ms": 90500, "sector1_ms": 30100, "sector2_ms": 29900, "sector3_ms": 30500, "lap_valid": True},
                        {"lap_number": 2, "lap_time_ms": 88000, "sector1_ms": 29200, "sector2_ms": 29100, "sector3_ms": 29700, "lap_valid": True},
                    ],
                },
                {
                    "vehicle_index": 1,
                    "best_lap_num": 2,
                    "best_s1_lap": 2,
                    "best_s2_lap": 2,
                    "best_s3_lap": 2,
                    "laps": [
                        {"lap_number": 1, "lap_time_ms": 91000, "sector1_ms": 30300, "sector2_ms": 30100, "sector3_ms": 30600, "lap_valid": True},
                        {"lap_number": 2, "lap_time_ms": 88500, "sector1_ms": 29400, "sector2_ms": 29300, "sector3_ms": 29800, "lap_valid": True},
                    ],
                },
            ],
        }
        history_response = self.client.post(
            "/api/telemetry/session-history",
            json=history_payload,
            headers=self.agent_headers(),
        )
        self.assertEqual(history_response.status_code, 200, history_response.text)

        for vehicle_index, lap_time_ms, slower in ((0, 88000, False), (1, 88500, True)):
            telemetry_response = self.client.post(
                "/api/telemetry/submit",
                json={
                    "race_id": race_id,
                    "vehicle_index": vehicle_index,
                    "lap_number": 2,
                    "lap_time_ms": lap_time_ms,
                    "samples": self._lap_samples(distance_shift=vehicle_index * 3.0, slower=slower),
                },
                headers=self.agent_headers(),
            )
            self.assertEqual(telemetry_response.status_code, 200, telemetry_response.text)

        return {
            "race_id": race_id,
            "web_user_id": owner["id"],
            "hero_player_id": hero_player_id,
        }

    def test_telemetry_analysis_endpoints_on_real_seeded_rows(self) -> None:
        seeded = self._seed_analysis_race()
        race_id = seeded["race_id"]

        compare = self.client.get(f"/api/telemetry/{race_id}/compare?a=0&b=1")
        self.assertEqual(compare.status_code, 200, compare.text)
        compare_payload = compare.json()
        self.assertEqual(compare_payload["a"]["lap_time_ms"], 88000)
        self.assertEqual(compare_payload["b"]["lap_time_ms"], 88500)
        self.assertIn("driver_name", compare_payload["a"])

        race_analysis = self.client.get(f"/api/telemetry/race-analysis/{race_id}")
        self.assertEqual(race_analysis.status_code, 200, race_analysis.text)
        analysis_payload = race_analysis.json()
        self.assertEqual(len(analysis_payload["drivers"]), 2)
        self.assertEqual(analysis_payload["drivers"][0]["theoretical_best_ms"], 88000)

        braking = self.client.get(f"/api/telemetry/braking-analysis/{race_id}")
        self.assertEqual(braking.status_code, 200, braking.text)
        self.assertGreaterEqual(len(braking.json()["drivers"][0]["zones"]), 1)
        self.assertTrue(braking.json()["drivers"][0]["zones"][0]["trail_braking"])

        throttle = self.client.get(f"/api/telemetry/throttle-analysis/{race_id}")
        self.assertEqual(throttle.status_code, 200, throttle.text)
        throttle_driver = throttle.json()["drivers"][0]
        self.assertGreater(throttle_driver["full_throttle_pct"], 0)
        self.assertGreater(throttle_driver["drs_pct"], 0)

        weather = self.client.get(f"/api/telemetry/weather-correlation/{race_id}")
        self.assertEqual(weather.status_code, 200, weather.text)
        weather_payload = weather.json()
        self.assertTrue(weather_payload["weather_changed"])
        self.assertEqual(weather_payload["weather_start"], "Clear")
        self.assertEqual(weather_payload["weather_end"], "Light Rain")

    def test_race_debrief_uses_linked_user_and_mocked_llm(self) -> None:
        seeded = self._seed_analysis_race()
        race_id = seeded["race_id"]
        captured_request: dict = {}

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"choices": [{"message": {"content": "Telemetry debrief summary"}}]}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, headers=None, json=None):
                captured_request["url"] = url
                captured_request["headers"] = headers
                captured_request["json"] = json
                return FakeResponse()

        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "integration-groq-key"}, clear=False):
            with mock.patch("httpx.AsyncClient", FakeAsyncClient):
                debrief = self.client.post(
                    f"/api/telemetry/race-analysis/{race_id}/debrief",
                    json={"web_user_id": seeded["web_user_id"], "question": "Разбери гонку"},
                )

        self.assertEqual(debrief.status_code, 200, debrief.text)
        self.assertEqual(debrief.json()["debrief"], "Telemetry debrief summary")
        self.assertEqual(captured_request["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertIn("THIS DRIVER", captured_request["json"]["messages"][1]["content"])
