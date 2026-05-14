from __future__ import annotations

import uuid
from unittest import mock

from tests.backend_integration_support import BackendIntegrationCase


class BackendRaceSubmitIntegrationTests(BackendIntegrationCase):
    def _create_season(self, token: str) -> int:
        lobby_response = self.client.post(
            "/api/lobby",
            json={"name": f"Race Lobby {uuid.uuid4().hex[:6]}", "description": "race submit"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(lobby_response.status_code, 200, lobby_response.text)
        lobby = lobby_response.json()

        season_response = self.client.post(
            f"/api/lobby/{lobby['id']}/seasons",
            json={"name": f"Race Season {uuid.uuid4().hex[:6]}"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(season_response.status_code, 200, season_response.text)
        return season_response.json()["id"]

    def _payload(self, season_id: int, session_uid: int) -> dict:
        return {
            "season_id": season_id,
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
                    "steam_name": "Background Driver",
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

    def test_race_submit_runs_background_tasks_after_commit(self) -> None:
        owner = self.register_user("race-bg-owner")
        season_id = self._create_season(owner["token"])
        events: list[tuple[str, int | None]] = []

        async def count_races(session_uid: int) -> int | None:
            from sqlalchemy import select
            from backend.db import base as db_base
            from backend.models.models import Race

            async with db_base.AsyncSessionLocal() as session:
                result = await session.execute(select(Race).where(Race.session_uid == session_uid))
                race = result.scalars().first()
                return race.id if race else None

        session_uid = 920000 + int(uuid.uuid4().hex[:6], 16)

        async def record_standings(season_id_value: int) -> None:
            events.append(("standings", await count_races(session_uid)))

        async def record_ratings(race_id: int) -> None:
            events.append(("ratings", race_id))

        async def record_notify(race_id: int, season_id_value: int, unresolved_players: list[str] | None = None) -> None:
            events.append(("notify", race_id))

        with mock.patch("backend.routers.races.recalc_standings", new=record_standings):
            with mock.patch("backend.routers.races._update_ratings", new=record_ratings):
                with mock.patch("backend.routers.races.notify_race_uploaded", new=record_notify):
                    response = self.client.post(
                        "/api/race/submit",
                        json=self._payload(season_id, session_uid),
                        headers=self.agent_headers(),
                    )

        self.assertEqual(response.status_code, 200, response.text)
        race_id = response.json()["race_id"]
        self.assertEqual(events, [("standings", race_id), ("ratings", race_id), ("notify", race_id)])

    def test_race_submit_survives_background_failures_and_keeps_committed_race(self) -> None:
        owner = self.register_user("race-bg-failure-owner")
        season_id = self._create_season(owner["token"])
        session_uid = 930000 + int(uuid.uuid4().hex[:6], 16)
        events: list[str] = []

        async def failing_standings(season_id_value: int) -> None:
            raise RuntimeError("forced standings failure")

        async def record_ratings(race_id: int) -> None:
            events.append("ratings")

        async def record_notify(race_id: int, season_id_value: int, unresolved_players: list[str] | None = None) -> None:
            events.append("notify")

        with mock.patch("backend.routers.races.recalc_standings", new=failing_standings):
            with mock.patch("backend.routers.races._update_ratings", new=record_ratings):
                with mock.patch("backend.routers.races.notify_race_uploaded", new=record_notify):
                    response = self.client.post(
                        "/api/race/submit",
                        json=self._payload(season_id, session_uid),
                        headers=self.agent_headers(),
                    )

        self.assertEqual(response.status_code, 200, response.text)
        race_id = response.json()["race_id"]
        self.assertEqual(events, ["ratings", "notify"])

        async def load_race(session):
            from sqlalchemy import select
            from backend.models.models import Race

            result = await session.execute(select(Race).where(Race.id == race_id))
            race = result.scalars().first()
            return race.session_uid if race else None

        self.assertEqual(self.harness.db_call(load_race), session_uid)

    def test_agent_can_lookup_race_by_session_uid_after_submit(self) -> None:
        owner = self.register_user("race-lookup-owner")
        season_id = self._create_season(owner["token"])
        session_uid = 940000 + int(uuid.uuid4().hex[:6], 16)

        with mock.patch("backend.routers.races.recalc_standings", new=mock.AsyncMock()):
            with mock.patch("backend.routers.races._update_ratings", new=mock.AsyncMock()):
                with mock.patch("backend.routers.races.notify_race_uploaded", new=mock.AsyncMock()):
                    submit_response = self.client.post(
                        "/api/race/submit",
                        json=self._payload(season_id, session_uid),
                        headers=self.agent_headers(),
                    )

        self.assertEqual(submit_response.status_code, 200, submit_response.text)
        race_id = submit_response.json()["race_id"]

        lookup_response = self.client.get(
            f"/api/race/session/{session_uid}",
            headers=self.agent_headers(),
        )

        self.assertEqual(lookup_response.status_code, 200, lookup_response.text)
        self.assertEqual(
            lookup_response.json(),
            {
                "status": "ok",
                "race_id": race_id,
                "season_id": season_id,
                "session_uid": session_uid,
                "round": submit_response.json()["round"],
                "track_id": 10,
                "track_name": submit_response.json()["track"],
                "raced_at": lookup_response.json()["raced_at"],
            },
        )
