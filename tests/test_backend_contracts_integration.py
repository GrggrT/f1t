from __future__ import annotations

import os
import uuid
from unittest import mock

from tests.backend_integration_support import (
    BackendIntegrationCase,
    LocalHTTPCaptureServer,
)


def _steam_id64() -> str:
    return str(76561190020000000 + int(uuid.uuid4().hex[:6], 16))


class BackendContractsIntegrationTests(BackendIntegrationCase):
    def _seed_contract_state(self) -> dict:
        async def seed(session):
            from backend.models.models import Player, Race, RaceResult, Season, SeasonContract
            from shared.f1_mappings import get_team

            current_season = Season(
                name=f"Contracts Current {uuid.uuid4().hex[:6]}",
                status="completed",
                calendar=[],
                points_system={},
            )
            next_season = Season(
                name=f"Contracts Next {uuid.uuid4().hex[:6]}",
                status="active",
                calendar=[],
                points_system={},
            )
            player = Player(
                name=f"Contracts Player {uuid.uuid4().hex[:4]}",
                steam_id64=_steam_id64(),
                steam_names=[f"Contracts Driver {uuid.uuid4().hex[:4]}"],
            )
            session.add_all([current_season, next_season, player])
            await session.flush()

            current_team_id = 7
            current_team = get_team(current_team_id)
            session.add(
                SeasonContract(
                    season_id=current_season.id,
                    player_id=player.id,
                    driver_id=18,
                    driver_name="Oliver Bearman",
                    team_id=current_team_id,
                    team_name=current_team["name"],
                )
            )

            race_one = Race(
                season_id=current_season.id,
                round_number=1,
                track_id=10,
                track_name="Silverstone",
                session_uid=960000 + int(uuid.uuid4().hex[:6], 16),
                packet_format=2025,
            )
            race_two = Race(
                season_id=current_season.id,
                round_number=2,
                track_id=11,
                track_name="Hungaroring",
                session_uid=970000 + int(uuid.uuid4().hex[:6], 16),
                packet_format=2025,
            )
            session.add_all([race_one, race_two])
            await session.flush()

            session.add_all(
                [
                    RaceResult(
                        race_id=race_one.id,
                        season_id=current_season.id,
                        vehicle_index=0,
                        is_human=True,
                        player_id=player.id,
                        driver_id=18,
                        driver_name="Oliver Bearman",
                        team_id=current_team_id,
                        team_name=current_team["name"],
                        grid_position=4,
                        position=1,
                        points=26.0,
                        result_status=3,
                    ),
                    RaceResult(
                        race_id=race_two.id,
                        season_id=current_season.id,
                        vehicle_index=0,
                        is_human=True,
                        player_id=player.id,
                        driver_id=18,
                        driver_name="Oliver Bearman",
                        team_id=current_team_id,
                        team_name=current_team["name"],
                        grid_position=3,
                        position=2,
                        points=18.0,
                        result_status=3,
                    ),
                ]
            )

            await session.commit()
            return {
                "current_season_id": current_season.id,
                "next_season_id": next_season.id,
                "player_id": player.id,
            }

        return self.harness.db_call(seed)

    def _prime_llm(self, server: LocalHTTPCaptureServer, total: int) -> None:
        for index in range(total):
            server.set_json_response(
                "/groq",
                {"choices": [{"message": {"content": f"Offer narrative {index + 1}"}}]},
            )

    def test_generate_contracts_background_notifies_bot_and_caches_offers(self) -> None:
        seeded = self._seed_contract_state()
        from backend.routers import contracts as contracts_router

        contracts_router._offers_cache.clear()

        with LocalHTTPCaptureServer() as server:
            self._prime_llm(server, 10)
            with mock.patch.dict(
                os.environ,
                {
                    "BOT_NOTIFY_URL": server.url("/internal/race_uploaded"),
                    "BOT_NOTIFY_SECRET": "contracts-secret",
                    "GROQ_API_KEY": "contracts-groq-key",
                    "GROQ_URL": server.url("/groq"),
                    "GROQ_MODEL": "contracts-model",
                },
                clear=False,
            ):
                admin_headers = self.auth_headers(self.make_system_admin_token("contracts-admin"))
                generate_response = self.client.post(
                    f"/api/contracts/generate/{seeded['current_season_id']}",
                    headers=admin_headers,
                )
                offers_response = self.client.get(f"/api/contracts/{seeded['current_season_id']}")

        self.assertEqual(generate_response.status_code, 200, generate_response.text)
        self.assertEqual(generate_response.json()["status"], "generating")
        self.assertEqual(offers_response.status_code, 200, offers_response.text)

        offers = offers_response.json()
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["player_id"], seeded["player_id"])
        self.assertGreaterEqual(len(offers[0]["offers"]), 2)
        self.assertTrue(all(offer["narrative"].startswith("Offer narrative") for offer in offers[0]["offers"]))

        groq_requests = server.requests_for("/groq")
        self.assertEqual(len(groq_requests), len(offers[0]["offers"]))
        self.assertTrue(all(request.headers["Authorization"] == "Bearer contracts-groq-key" for request in groq_requests))
        self.assertTrue(all(request.json()["model"] == "contracts-model" for request in groq_requests))

        contracts_ready = server.requests_for("/internal/contracts_ready")[0]
        self.assertEqual(contracts_ready.headers["X-Secret"], "contracts-secret")
        contracts_ready_payload = contracts_ready.json()
        self.assertEqual(contracts_ready_payload["season_id"], seeded["current_season_id"])
        self.assertEqual(contracts_ready_payload["offers"], offers)

    def test_get_contracts_sync_generation_and_accept_persists_contract(self) -> None:
        seeded = self._seed_contract_state()
        from backend.routers import contracts as contracts_router

        contracts_router._offers_cache.clear()

        with LocalHTTPCaptureServer() as server:
            self._prime_llm(server, 10)
            with mock.patch.dict(
                os.environ,
                {
                    "GROQ_API_KEY": "contracts-groq-key",
                    "GROQ_URL": server.url("/groq"),
                    "GROQ_MODEL": "contracts-model",
                },
                clear=False,
            ):
                offers_response = self.client.get(f"/api/contracts/{seeded['current_season_id']}")

        self.assertEqual(offers_response.status_code, 200, offers_response.text)
        offers = offers_response.json()
        selected_offer = offers[0]["offers"][0]

        accept_response = self.client.post(
            "/api/contracts/accept",
            json={
                "player_id": seeded["player_id"],
                "team_id": selected_offer["team_id"],
                "new_season_id": seeded["next_season_id"],
            },
            headers=self.auth_headers(self.make_system_admin_token("contracts-accept")),
        )
        self.assertEqual(accept_response.status_code, 200, accept_response.text)
        self.assertEqual(accept_response.json()["team_name"], selected_offer["team_name"])

        async def load_contract(session):
            from sqlalchemy import select
            from backend.models.models import SeasonContract

            result = await session.execute(
                select(SeasonContract).where(
                    SeasonContract.season_id == seeded["next_season_id"],
                    SeasonContract.player_id == seeded["player_id"],
                )
            )
            contract = result.scalars().first()
            if not contract:
                return None
            return {
                "team_id": contract.team_id,
                "team_name": contract.team_name,
                "driver_name": contract.driver_name,
            }

        persisted = self.harness.db_call(load_contract)
        self.assertEqual(
            persisted,
            {
                "team_id": selected_offer["team_id"],
                "team_name": selected_offer["team_name"],
                "driver_name": accept_response.json()["driver_name"],
            },
        )
