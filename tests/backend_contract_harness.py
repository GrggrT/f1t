from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.db.base import get_db
from backend.models.models import LapTelemetry, Lobby, Race, RaceResult, RaceSessionHistory, Season, User
from backend.routers import lobby, races, telemetry
from backend.services.auth_dependencies import get_current_user, get_current_user_optional, verify_agent_token


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass
class SmokeCheck:
    name: str
    ok: bool
    details: dict[str, Any]


class _FakeScalarAccessor:
    def __init__(self, first_value=None, values: list[Any] | None = None):
        self._first_value = first_value
        self._values = list(values or ([] if first_value is None else [first_value]))

    def first(self):
        return self._first_value

    def all(self):
        return list(self._values)


class _FakeResult:
    def __init__(
        self,
        *,
        first_value=None,
        all_values: list[Any] | None = None,
        scalar_value=None,
        scalar_values: list[Any] | None = None,
    ):
        self._first_value = first_value
        self._all_values = list(all_values or ([] if first_value is None else [first_value]))
        self._scalar_value = scalar_value if scalar_value is not None else first_value
        self._scalar_accessor = _FakeScalarAccessor(first_value, scalar_values if scalar_values is not None else self._all_values)

    def scalars(self) -> _FakeScalarAccessor:
        return self._scalar_accessor

    def first(self):
        return self._first_value

    def all(self):
        return list(self._all_values)

    def scalar(self):
        return self._scalar_value


class _FakeAsyncSession:
    def __init__(self, execute_results: list[_FakeResult]):
        self._execute_results = list(execute_results)
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    async def execute(self, query):
        if not self._execute_results:
            raise AssertionError(f"Unexpected execute() call for query: {query}")
        return self._execute_results.pop(0)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        next_race_id = 100
        for obj in self.added:
            if isinstance(obj, Race) and getattr(obj, "id", None) is None:
                obj.id = next_race_id
                next_race_id += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def _build_app(
    *routers,
    db: _FakeAsyncSession,
    user: User | None = None,
    optional_user: User | None = None,
) -> FastAPI:
    app = FastAPI()
    for router in routers:
        app.include_router(router)

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[verify_agent_token] = lambda: True
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    if optional_user is not None:
        app.dependency_overrides[get_current_user_optional] = lambda: optional_user
    return app


def _race_submit_payload() -> dict[str, Any]:
    return {
        "season_id": 1,
        "session_uid": 555001,
        "packet_format": 2025,
        "track_id": 10,
        "weather_start": 0,
        "weather_end": 1,
        "total_laps": 58,
        "air_temp": 25,
        "track_temp": 33,
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
                "best_lap_ms": 88111,
                "penalties_time": 0,
                "num_penalties": 0,
                "num_pit_stops": 1,
                "tyre_stints": [{"compound": "Soft", "laps": 12}],
                "has_fastest_lap": True,
            }
        ],
        "events": [{"event_code": "FTLP", "event_data": {"vehicleIdx": 0}}],
    }


def _check_race_submit_contract() -> SmokeCheck:
    db = _FakeAsyncSession([_FakeResult(first_value=None)])
    app = _build_app(races.router, db=db)

    async def _fake_detect_round(*_args, **_kwargs):
        return 5, "new"

    async def _fake_resolve_participants(*_args, **_kwargs):
        return {0: 99}, ["Ghost Driver"]

    with mock.patch("backend.routers.races.detect_round", new=_fake_detect_round):
        with mock.patch("backend.routers.races.resolve_participants", new=_fake_resolve_participants):
            with mock.patch("backend.routers.races.recalc_standings", new=mock.AsyncMock()):
                with mock.patch("backend.routers.races._update_ratings", new=mock.AsyncMock()):
                    with mock.patch("backend.routers.races.notify_race_uploaded", new=mock.AsyncMock()):
                        response = TestClient(app).post("/api/race/submit", json=_race_submit_payload())

    payload = response.json()
    ok = (
        response.status_code == 200
        and payload.get("status") == "ok"
        and isinstance(payload.get("race_id"), int)
        and payload.get("round") == 5
        and bool(payload.get("track"))
        and payload.get("unresolved_players") == ["Ghost Driver"]
    )
    return SmokeCheck(
        name="race_submit_contract",
        ok=ok,
        details={
            "status_code": response.status_code,
            "status": payload.get("status"),
            "race_id": payload.get("race_id"),
            "round": payload.get("round"),
            "track": payload.get("track"),
            "unresolved_players": payload.get("unresolved_players"),
        },
    )


def _check_telemetry_submit_alias_contract() -> SmokeCheck:
    db = _FakeAsyncSession([
        _FakeResult(first_value=None),
        _FakeResult(first_value=None),
    ])
    app = _build_app(telemetry.router, db=db)
    response = TestClient(app).post(
        "/api/telemetry/submit",
        json={
            "race_id": 77,
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
                    "str": 0.12,
                }
            ],
        },
    )

    added_lap = next((obj for obj in db.added if isinstance(obj, LapTelemetry)), None)
    stored_samples = added_lap.samples if added_lap else []
    stored_steer = stored_samples[0].get("steer") if stored_samples else None
    payload = response.json()
    ok = response.status_code == 200 and payload.get("status") == "ok" and stored_steer == 0.12
    return SmokeCheck(
        name="telemetry_submit_alias_contract",
        ok=ok,
        details={
            "status_code": response.status_code,
            "status": payload.get("status"),
            "stored_steer": stored_steer,
            "stored_sample_keys": sorted(stored_samples[0].keys()) if stored_samples else [],
        },
    )


def _check_best_lap_route_contract() -> SmokeCheck:
    history_row = RaceSessionHistory(
        race_id=77,
        vehicle_index=0,
        best_lap_num=1,
        laps=[
            {
                "lap_number": 1,
                "lap_time_ms": 88000,
                "sector1_ms": 29000,
                "sector2_ms": 29000,
                "sector3_ms": 30000,
                "lap_valid": True,
            }
        ],
    )
    lap_row = LapTelemetry(
        race_id=77,
        vehicle_index=0,
        lap_number=1,
        lap_time_ms=None,
        samples=[{"t": 1.0, "x": 0.0, "z": 0.0, "steer": 0.12}],
    )
    db = _FakeAsyncSession([
        _FakeResult(first_value=history_row),
        _FakeResult(all_values=[lap_row], scalar_values=[lap_row]),
    ])
    app = _build_app(telemetry.router, db=db)
    response = TestClient(app).get("/api/telemetry/77/0/best")

    payload = response.json()
    ok = response.status_code == 200 and payload.get("lap_number") == 1 and payload.get("lap_time_ms") == 88000
    return SmokeCheck(
        name="telemetry_best_route_contract",
        ok=ok,
        details={
            "status_code": response.status_code,
            "lap_number": payload.get("lap_number"),
            "lap_time_ms": payload.get("lap_time_ms"),
        },
    )


def _check_session_history_overview_contract() -> SmokeCheck:
    history_row = RaceSessionHistory(
        race_id=77,
        vehicle_index=0,
        best_lap_num=1,
        best_s1_lap=1,
        best_s2_lap=1,
        best_s3_lap=1,
        laps=[
            {
                "lap_number": 1,
                "lap_time_ms": 88000,
                "sector1_ms": 29000,
                "sector2_ms": 29000,
                "sector3_ms": 30000,
                "lap_valid": True,
            }
        ],
    )
    result_row = RaceResult(
        race_id=77,
        vehicle_index=0,
        driver_id=1,
        driver_name="Alice",
        team_id=2,
        team_name="Team A",
        is_human=True,
    )
    db = _FakeAsyncSession([
        _FakeResult(all_values=[history_row], scalar_values=[history_row]),
        _FakeResult(all_values=[result_row], scalar_values=[result_row]),
    ])
    app = _build_app(telemetry.router, db=db)
    response = TestClient(app).get("/api/telemetry/77/session-history")

    payload = response.json()
    first_row = payload[0] if payload else {}
    ok = (
        response.status_code == 200
        and isinstance(payload, list)
        and first_row.get("driver_name") == "Alice"
        and "team_color" in first_row
        and first_row.get("is_human") is True
        and first_row.get("laps", [{}])[0].get("lap_time_ms") == 88000
    )
    return SmokeCheck(
        name="telemetry_session_history_contract",
        ok=ok,
        details={
            "status_code": response.status_code,
            "rows": len(payload) if isinstance(payload, list) else None,
            "first_row": first_row,
        },
    )


def _check_host_seasons_contract() -> SmokeCheck:
    lobby_row = Lobby(id=10, name="Night League", description="Core lobby", creator_user_id=7)
    season_completed = Season(
        id=201,
        name="Season Completed",
        status="completed",
        calendar=[{"round": 1}],
        creator_user_id=7,
        lobby_id=10,
        created_at=_now(),
    )
    season_active = Season(
        id=202,
        name="Season Active",
        status="active",
        calendar=[{"round": 1}, {"round": 2}],
        creator_user_id=7,
        lobby_id=10,
        created_at=_now(),
    )
    db = _FakeAsyncSession([
        _FakeResult(
            all_values=[
                (season_completed, lobby_row, "admin"),
                (season_active, lobby_row, "member"),
            ],
            scalar_values=[],
        ),
        _FakeResult(scalar_value=5),
        _FakeResult(scalar_value=1),
    ])
    user = User(id=7, name="Launcher User")
    app = _build_app(lobby.router, db=db, user=user)
    response = TestClient(app).get("/api/lobby/host-seasons")

    payload = response.json()
    ok = (
        response.status_code == 200
        and [item.get("id") for item in payload] == [202, 201]
        and payload[0].get("can_manage") is False
        and payload[1].get("can_manage") is True
        and payload[0].get("lobby_name") == "Night League"
    )
    return SmokeCheck(
        name="host_seasons_contract",
        ok=ok,
        details={
            "status_code": response.status_code,
            "order": [item.get("id") for item in payload],
            "first": payload[0] if payload else None,
            "second": payload[1] if len(payload) > 1 else None,
        },
    )


def run_smoke_checks() -> dict[str, Any]:
    checks = [
        _check_race_submit_contract(),
        _check_telemetry_submit_alias_contract(),
        _check_best_lap_route_contract(),
        _check_session_history_overview_contract(),
        _check_host_seasons_contract(),
    ]
    serialized = [asdict(check) for check in checks]
    return {
        "all_passed": all(check["ok"] for check in serialized),
        "checks": serialized,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic backend contract smoke checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    summary = run_smoke_checks()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        for check in summary["checks"]:
            status = "PASS" if check["ok"] else "FAIL"
            print(f"[{status}] {check['name']}")
            if not check["ok"]:
                print(json.dumps(check["details"], ensure_ascii=False, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
