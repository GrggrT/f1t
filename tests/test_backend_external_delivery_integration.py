from __future__ import annotations

import os
import uuid
from unittest import mock

from tests.backend_integration_support import (
    BackendIntegrationCase,
    LocalHTTPCaptureServer,
)


def _steam_id64() -> str:
    return str(76561190010000000 + int(uuid.uuid4().hex[:6], 16))


class BackendExternalDeliveryIntegrationTests(BackendIntegrationCase):
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

    def _create_season(self, token: str) -> int:
        lobby_response = self.client.post(
            "/api/lobby",
            json={"name": f"Delivery Lobby {uuid.uuid4().hex[:6]}", "description": "delivery"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(lobby_response.status_code, 200, lobby_response.text)
        lobby = lobby_response.json()

        season_response = self.client.post(
            f"/api/lobby/{lobby['id']}/seasons",
            json={"name": f"Delivery Season {uuid.uuid4().hex[:6]}"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(season_response.status_code, 200, season_response.text)
        return season_response.json()["id"]

    def _race_payload(self, season_id: int, steam_name: str) -> dict:
        return {
            "season_id": season_id,
            "session_uid": 950000 + int(uuid.uuid4().hex[:6], 16),
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
                    "steam_name": steam_name,
                    "driver_id": 1,
                    "team_id": 2,
                    "grid_position": 2,
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

    def test_race_submit_delivers_bot_callbacks_and_ai_debrief_over_real_http(self) -> None:
        owner = self.register_user("delivery-owner")
        driver_name = f"Delivery Driver {uuid.uuid4().hex[:4]}"
        telegram_id = 700000 + int(uuid.uuid4().hex[:6], 16)
        self._insert_player("Delivery Player", driver_name, telegram_id=telegram_id)
        season_id = self._create_season(owner["token"])

        with LocalHTTPCaptureServer() as server:
            server.set_json_response(
                "/groq",
                {"choices": [{"message": {"content": "Integration debrief text"}}]},
            )

            env = {
                "BOT_NOTIFY_URL": server.url("/internal/race_uploaded"),
                "BOT_NOTIFY_SECRET": "delivery-secret",
                "BOT_NOTIFY_DELAY_SEC": "0",
                "GROQ_API_KEY": "delivery-groq-key",
                "GROQ_URL": server.url("/groq"),
                "GROQ_MODEL": "integration-model",
                "AI_ENGINEER_STAGGER_SEC": "0",
            }

            with mock.patch.dict(os.environ, env, clear=False):
                with mock.patch("backend.routers.races.recalc_standings", new=mock.AsyncMock()):
                    with mock.patch("backend.routers.races._update_ratings", new=mock.AsyncMock()):
                        with mock.patch(
                            "backend.services.achievement_engine.check_achievements_after_race",
                            new=mock.AsyncMock(return_value=[{"code": "win"}]),
                        ):
                            with mock.patch(
                                "backend.services.fun_stats.compute_fun_stats",
                                new=mock.AsyncMock(return_value={"clean_race": 1}),
                            ):
                                response = self.client.post(
                                    "/api/race/submit",
                                    json=self._race_payload(season_id, driver_name),
                                    headers=self.agent_headers(),
                                )

        self.assertEqual(response.status_code, 200, response.text)
        race_id = response.json()["race_id"]
        track_name = response.json()["track"]

        paths = [request.path for request in server.all_requests()]
        self.assertEqual(paths, ["/internal/race_uploaded", "/groq", "/internal/debrief"])

        race_uploaded = server.requests_for("/internal/race_uploaded")[0]
        self.assertEqual(race_uploaded.headers["X-Secret"], "delivery-secret")
        self.assertEqual(
            race_uploaded.json(),
            {
                "race_id": race_id,
                "season_id": season_id,
                "unresolved_players": [],
                "achievements": [{"code": "win"}],
                "fun_stats": {"clean_race": 1},
            },
        )

        groq_request = server.requests_for("/groq")[0]
        groq_payload = groq_request.json()
        self.assertEqual(groq_request.headers["Authorization"], "Bearer delivery-groq-key")
        self.assertEqual(groq_payload["model"], "integration-model")
        self.assertIn("Delivery Player", groq_payload["messages"][1]["content"])

        debrief_request = server.requests_for("/internal/debrief")[0]
        self.assertEqual(debrief_request.headers["X-Secret"], "delivery-secret")
        self.assertEqual(
            debrief_request.json(),
            {
                "telegram_id": telegram_id,
                "player_name": "Delivery Player",
                "track_name": track_name,
                "debrief": "Integration debrief text",
            },
        )

    def test_engineer_proxy_uses_real_outbound_groq_call(self) -> None:
        with LocalHTTPCaptureServer() as server:
            server.set_json_response(
                "/groq",
                {"choices": [{"message": {"content": "Engineer proxy answer"}}]},
            )

            with mock.patch.dict(
                os.environ,
                {
                    "GROQ_API_KEY": "proxy-groq-key",
                    "GROQ_URL": server.url("/groq"),
                    "GROQ_MODEL": "proxy-model",
                },
                clear=False,
            ):
                response = self.client.post(
                    "/api/engineer/ask",
                    json={"question": "Where am I losing time?", "system_prompt": "x" * 60},
                    headers=self.auth_headers(self.make_system_admin_token("engineer-proxy")),
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["answer"], "Engineer proxy answer")

        request = server.requests_for("/groq")[0]
        payload = request.json()
        self.assertEqual(request.headers["Authorization"], "Bearer proxy-groq-key")
        self.assertEqual(payload["model"], "proxy-model")
        self.assertEqual(payload["messages"][1]["content"], "Where am I losing time?")
