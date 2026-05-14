from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile
import uuid
from unittest import mock

from tests.backend_integration_support import BackendIntegrationCase


class BackendWsAndConcurrencyIntegrationTests(BackendIntegrationCase):
    def _create_season(self, token: str) -> int:
        lobby_response = self.client.post(
            "/api/lobby",
            json={"name": f"WS Lobby {uuid.uuid4().hex[:6]}", "description": "ws and concurrency"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(lobby_response.status_code, 200, lobby_response.text)
        lobby = lobby_response.json()

        season_response = self.client.post(
            f"/api/lobby/{lobby['id']}/seasons",
            json={"name": f"WS Season {uuid.uuid4().hex[:6]}"},
            headers=self.auth_headers(token),
        )
        self.assertEqual(season_response.status_code, 200, season_response.text)
        return season_response.json()["id"]

    def _race_payload(self, season_id: int, session_uid: int) -> dict:
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
                    "steam_name": "Concurrency Driver",
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

    def test_websocket_client_receives_live_agent_updates_and_last_snapshot(self) -> None:
        from backend.routers import ws as ws_router

        ws_router.reset_ws_state()

        status_payload = {
            "type": "agent_status",
            "state": "RACING",
            "track_name": "Silverstone",
            "label": "Lap 7",
            "track_id": 10,
        }
        live_payload = {
            "type": "live_data",
            "entries": [{"driver": "Max Verstappen", "lap": 7, "gap": 0.0}],
        }

        with self.client.websocket_connect("/ws/client") as first_client:
            with self.client.websocket_connect(f"/ws/agent?token={os.environ['AGENT_SECRET_TOKEN']}") as agent:
                agent.send_json(
                    {
                        "type": "status",
                        "state": "RACING",
                        "track_name": "Silverstone",
                        "label": "Lap 7",
                        "track_id": 10,
                    }
                )
                self.assertEqual(first_client.receive_json(), status_payload)

                agent.send_json({"type": "live_data", "entries": live_payload["entries"]})
                self.assertEqual(first_client.receive_json(), live_payload)

            with self.client.websocket_connect("/ws/client") as second_client:
                self.assertEqual(second_client.receive_json(), status_payload)
                self.assertEqual(second_client.receive_json(), live_payload)

    def test_live_snapshot_http_endpoints_survive_ws_state_reset(self) -> None:
        from backend.routers import ws as ws_router

        status_payload = {
            "type": "agent_status",
            "state": "race",
            "track_name": "Spa-Francorchamps",
            "label": "Race",
            "track_id": 11,
        }
        live_payload = {
            "type": "live_data",
            "entries": [{"driver_name": "Charles Leclerc", "lap": 12, "gap": "leader"}],
        }

        with tempfile.TemporaryDirectory() as runtime_dir:
            with mock.patch.dict(os.environ, {"BACKEND_RUNTIME_DIR": runtime_dir}, clear=False):
                ws_router.reset_ws_state()

                with self.client.websocket_connect(f"/ws/agent?token={os.environ['AGENT_SECRET_TOKEN']}") as agent:
                    agent.send_json(
                        {
                            "type": "status",
                            "state": status_payload["state"],
                            "track_name": status_payload["track_name"],
                            "label": status_payload["label"],
                            "track_id": status_payload["track_id"],
                        }
                    )
                    agent.send_json({"type": "live_data", "entries": live_payload["entries"]})

                snapshot_response = self.client.get("/api/live/snapshot")
                self.assertEqual(snapshot_response.status_code, 200, snapshot_response.text)
                snapshot = snapshot_response.json()
                self.assertEqual(snapshot["status"], status_payload)
                self.assertEqual(snapshot["live"], live_payload)
                self.assertIsInstance(snapshot["updated_at"], str)

                status_response = self.client.get("/api/live/status")
                self.assertEqual(status_response.status_code, 200, status_response.text)
                self.assertEqual(status_response.json(), status_payload)

                data_response = self.client.get("/api/live/data")
                self.assertEqual(data_response.status_code, 200, data_response.text)
                self.assertEqual(data_response.json(), live_payload)

                ws_router.reset_ws_state(clear_persisted=False)

                persisted_response = self.client.get("/api/live/snapshot")
                self.assertEqual(persisted_response.status_code, 200, persisted_response.text)
                persisted_snapshot = persisted_response.json()
                self.assertEqual(persisted_snapshot["status"], status_payload)
                self.assertEqual(persisted_snapshot["live"], live_payload)

                with self.client.websocket_connect("/ws/client") as client:
                    self.assertEqual(client.receive_json(), status_payload)
                    self.assertEqual(client.receive_json(), live_payload)

                ws_router.reset_ws_state()

    def test_concurrent_duplicate_race_submit_keeps_single_row(self) -> None:
        owner = self.register_user("ws-concurrency-owner")
        season_id = self._create_season(owner["token"])
        session_uid = 980000 + int(uuid.uuid4().hex[:6], 16)

        async def delayed_detect_round(db, season_id_value, track_id, session_uid_value):
            await asyncio.sleep(0.05)
            return 1, "ok"

        def submit_once() -> tuple[int, dict]:
            response = self.client.post(
                "/api/race/submit",
                headers=self.agent_headers(),
                json=self._race_payload(season_id, session_uid),
            )
            return response.status_code, response.json()

        with mock.patch("backend.routers.races.detect_round", new=delayed_detect_round):
            with mock.patch("backend.routers.races.recalc_standings", new=mock.AsyncMock()):
                with mock.patch("backend.routers.races._update_ratings", new=mock.AsyncMock()):
                    with mock.patch("backend.routers.races.notify_race_uploaded", new=mock.AsyncMock()):
                        with ThreadPoolExecutor(max_workers=10) as executor:
                            responses = list(executor.map(lambda _: submit_once(), range(10)))

        self.assertTrue(all(status_code == 200 for status_code, _ in responses))
        payloads = [payload for _, payload in responses]

        statuses = [payload["status"] for payload in payloads]
        self.assertEqual(statuses.count("ok"), 1)
        self.assertEqual(statuses.count("duplicate"), 9)
        self.assertEqual(len({payload["race_id"] for payload in payloads}), 1)

        async def count_races(session):
            from sqlalchemy import select
            from backend.models.models import Race

            result = await session.execute(select(Race).where(Race.session_uid == session_uid))
            return len(result.scalars().all())

        self.assertEqual(self.harness.db_call(count_races), 1)

    def test_concurrent_duplicate_telemetry_submit_keeps_single_lap_row(self) -> None:
        owner = self.register_user("ws-telemetry-owner")
        season_id = self._create_season(owner["token"])
        session_uid = 990000 + int(uuid.uuid4().hex[:6], 16)

        with mock.patch("backend.routers.races.recalc_standings", new=mock.AsyncMock()):
            with mock.patch("backend.routers.races._update_ratings", new=mock.AsyncMock()):
                with mock.patch("backend.routers.races.notify_race_uploaded", new=mock.AsyncMock()):
                    submit_response = self.client.post(
                        "/api/race/submit",
                        headers=self.agent_headers(),
                        json=self._race_payload(season_id, session_uid),
                    )

        self.assertEqual(submit_response.status_code, 200, submit_response.text)
        race_id = submit_response.json()["race_id"]
        payload = {
            "race_id": race_id,
            "vehicle_index": 0,
            "lap_number": 1,
            "lap_time_ms": 88000,
            "samples": [
                {
                    "t": 1.0,
                    "x": 10.0,
                    "z": 20.0,
                    "spd": 300,
                    "thr": 1.0,
                    "brk": 0.0,
                    "gear": 8,
                    "drs": 1,
                    "dist": 100.0,
                }
            ],
        }

        def submit_once() -> tuple[int, dict]:
            response = self.client.post(
                "/api/telemetry/submit",
                headers=self.agent_headers(),
                json=payload,
            )
            return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=10) as executor:
            responses = list(executor.map(lambda _: submit_once(), range(10)))

        self.assertTrue(all(status_code == 200 for status_code, _ in responses))
        statuses = {body["status"] for _, body in responses}
        self.assertTrue(statuses.issubset({"ok", "duplicate", "updated"}))

        async def count_laps(session):
            from sqlalchemy import select
            from backend.models.models import LapTelemetry

            result = await session.execute(
                select(LapTelemetry).where(
                    LapTelemetry.race_id == race_id,
                    LapTelemetry.vehicle_index == 0,
                    LapTelemetry.lap_number == 1,
                )
            )
            return len(result.scalars().all())

        self.assertEqual(self.harness.db_call(count_laps), 1)
