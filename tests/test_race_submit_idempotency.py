from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError

from backend.models.models import Race
from backend.routers.races import ParticipantSubmit, RaceSubmit, submit_race


class _FakeScalarResult:
    def __init__(self, first_value=None, all_values=None):
        self._first_value = first_value
        self._all_values = list(all_values or ([] if first_value is None else [first_value]))

    def scalars(self) -> "_FakeScalarResult":
        return self

    def first(self):
        return self._first_value

    def all(self):
        return list(self._all_values)


class _FakeAsyncSession:
    def __init__(self, execute_results: list[_FakeScalarResult], *, flush_exc: Exception | None = None):
        self._execute_results = list(execute_results)
        self._flush_exc = flush_exc
        self.added: list[object] = []
        self.rollback_calls = 0
        self.commit_calls = 0

    async def execute(self, query):
        if not self._execute_results:
            raise AssertionError("Unexpected execute() call")
        return self._execute_results.pop(0)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        if self._flush_exc is not None:
            raise self._flush_exc

        for obj in self.added:
            if isinstance(obj, Race) and getattr(obj, "id", None) is None:
                obj.id = 999

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def _payload(session_uid: int = 444) -> RaceSubmit:
    return RaceSubmit(
        season_id=1,
        session_uid=session_uid,
        packet_format=2025,
        track_id=10,
        weather_start=0,
        weather_end=1,
        total_laps=58,
        air_temp=24,
        track_temp=31,
        participants=[
            ParticipantSubmit(
                vehicle_index=0,
                is_human=True,
                steam_name="Driver One",
                driver_id=1,
                team_id=2,
                grid_position=1,
                position=1,
                result_status=3,
                total_race_time=5000.5,
                best_lap_ms=88_111,
                penalties_time=0,
                num_penalties=0,
                num_pit_stops=1,
                tyre_stints=[],
                has_fastest_lap=True,
            )
        ],
        events=[],
    )


class RaceSubmitIdempotencyTests(unittest.TestCase):
    def test_existing_session_uid_returns_duplicate_with_existing_race_details(self):
        existing = Race(id=77, round_number=5, track_name="Bahrain", session_uid=444)
        db = _FakeAsyncSession([_FakeScalarResult(existing)])

        result = asyncio.run(
            submit_race(
                _payload(),
                BackgroundTasks(),
                db=db,
                _=True,
            )
        )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["race_id"], 77)
        self.assertEqual(result["round"], 5)
        self.assertEqual(result["track"], "Bahrain")

    def test_integrity_error_during_insert_is_normalized_to_duplicate_response(self):
        integrity_error = IntegrityError("insert into races", {}, Exception("duplicate session_uid"))
        existing = Race(id=88, round_number=6, track_name="Jeddah", session_uid=555)
        db = _FakeAsyncSession(
            [
                _FakeScalarResult(None),
                _FakeScalarResult(existing),
            ],
            flush_exc=integrity_error,
        )

        with mock.patch("backend.routers.races.detect_round", new=mock.AsyncMock(return_value=(6, "new"))):
            with mock.patch("backend.routers.races.resolve_participants", new=mock.AsyncMock(return_value=({}, []))):
                result = asyncio.run(
                    submit_race(
                        _payload(session_uid=555),
                        BackgroundTasks(),
                        db=db,
                        _=True,
                    )
                )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["race_id"], 88)
        self.assertEqual(result["round"], 6)
        self.assertEqual(result["track"], "Jeddah")
        self.assertEqual(db.rollback_calls, 1)
        self.assertEqual(db.commit_calls, 0)


if __name__ == "__main__":
    unittest.main()
