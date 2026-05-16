"""
POST /api/telemetry/submit               — приём телеметрии от агента (один круг)
POST /api/telemetry/session-history      — приём секторных времён от агента
GET  /api/telemetry/{race_id}            — доступные круги по пилотам
GET  /api/telemetry/{race_id}/{vidx}/{lap} — данные одного круга
GET  /api/telemetry/{race_id}/{vidx}/best  — лучший круг пилота
GET  /api/telemetry/{race_id}/compare      — сравнение двух пилотов (лучшие круги)
GET  /api/race/{race_id}/analysis          — полный race analysis
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, ConfigDict, Field

from backend.db.base import get_db
from backend.models.models import LapTelemetry, RaceResult, RaceSessionHistory, Race, User
from backend.services.auth_dependencies import get_current_user, verify_agent_token

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TelemetrySample(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    t:     float
    x:     float
    z:     float
    spd:   int
    thr:   float
    brk:   float
    gear:  int
    drs:   int
    dist:  float
    ers:   float = 0.0    # ERS deployed this lap (MJ)
    steer: float = Field(default=0.0, alias="str")    # Steering -1.0 to 1.0 (sent as "str" from agent)
    fuel:  float = 0.0    # Fuel in tank (kg)
    tw:    float = 0.0    # Average tyre wear %


class LapSubmit(BaseModel):
    race_id:       int
    vehicle_index: int
    lap_number:    int
    lap_time_ms:   int | None = None
    samples:       list[TelemetrySample]


class SessionHistoryLap(BaseModel):
    lap_number:  int
    lap_time_ms: int
    sector1_ms:  int
    sector2_ms:  int
    sector3_ms:  int
    lap_valid:   bool = True


class VehicleHistory(BaseModel):
    vehicle_index: int
    best_lap_num:  int = 0
    best_s1_lap:   int = 0
    best_s2_lap:   int = 0
    best_s3_lap:   int = 0
    laps:          list[SessionHistoryLap]


class SessionHistorySubmit(BaseModel):
    race_id:  int
    vehicles: list[VehicleHistory]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _positive_lap_time(value: int | None) -> int | None:
    try:
        parsed = int(value) if value is not None else 0
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _history_laps_by_number(laps: list[dict] | None) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for lap in laps or []:
        if not isinstance(lap, dict):
            continue
        lap_number = int(lap.get("lap_number", 0) or 0)
        if lap_number <= 0:
            continue
        result[lap_number] = {
            "lap_number": lap_number,
            "lap_time_ms": _positive_lap_time(lap.get("lap_time_ms")) or 0,
            "sector1_ms": _positive_lap_time(lap.get("sector1_ms")) or 0,
            "sector2_ms": _positive_lap_time(lap.get("sector2_ms")) or 0,
            "sector3_ms": _positive_lap_time(lap.get("sector3_ms")) or 0,
            "lap_valid": bool(lap.get("lap_valid", True)),
        }
    return result


def _merge_history_laps(existing_laps: list[dict] | None, incoming_laps: list[dict]) -> list[dict]:
    merged = _history_laps_by_number(existing_laps)
    for lap in incoming_laps:
        lap_number = int(lap.get("lap_number", 0) or 0)
        if lap_number <= 0:
            continue
        current = merged.get(lap_number, {})
        merged[lap_number] = {
            "lap_number": lap_number,
            "lap_time_ms": _positive_lap_time(lap.get("lap_time_ms")) or _positive_lap_time(current.get("lap_time_ms")) or 0,
            "sector1_ms": _positive_lap_time(lap.get("sector1_ms")) or _positive_lap_time(current.get("sector1_ms")) or 0,
            "sector2_ms": _positive_lap_time(lap.get("sector2_ms")) or _positive_lap_time(current.get("sector2_ms")) or 0,
            "sector3_ms": _positive_lap_time(lap.get("sector3_ms")) or _positive_lap_time(current.get("sector3_ms")) or 0,
            "lap_valid": bool(lap.get("lap_valid", current.get("lap_valid", True))),
        }
    return [merged[key] for key in sorted(merged)]


def _serialize_history_row(row: RaceSessionHistory | dict | None) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return {
            "vehicle_index": int(row.get("vehicle_index", 0) or 0),
            "best_lap_num": int(row.get("best_lap_num", 0) or 0),
            "best_s1_lap": int(row.get("best_s1_lap", 0) or 0),
            "best_s2_lap": int(row.get("best_s2_lap", 0) or 0),
            "best_s3_lap": int(row.get("best_s3_lap", 0) or 0),
            "laps": _merge_history_laps([], row.get("laps", [])),
        }
    return {
        "vehicle_index": row.vehicle_index,
        "best_lap_num": row.best_lap_num or 0,
        "best_s1_lap": row.best_s1_lap or 0,
        "best_s2_lap": row.best_s2_lap or 0,
        "best_s3_lap": row.best_s3_lap or 0,
        "laps": _merge_history_laps([], row.laps or []),
    }


def _merge_history_row(existing: RaceSessionHistory, vehicle_history: VehicleHistory) -> bool:
    incoming_laps = [_model_dump(lap) for lap in vehicle_history.laps]
    merged_laps = _merge_history_laps(existing.laps or [], incoming_laps)
    changed = merged_laps != (existing.laps or [])

    best_lap_num = vehicle_history.best_lap_num or existing.best_lap_num or 0
    best_s1_lap = vehicle_history.best_s1_lap or existing.best_s1_lap or 0
    best_s2_lap = vehicle_history.best_s2_lap or existing.best_s2_lap or 0
    best_s3_lap = vehicle_history.best_s3_lap or existing.best_s3_lap or 0

    if best_lap_num != (existing.best_lap_num or 0):
        existing.best_lap_num = best_lap_num
        changed = True
    if best_s1_lap != (existing.best_s1_lap or 0):
        existing.best_s1_lap = best_s1_lap
        changed = True
    if best_s2_lap != (existing.best_s2_lap or 0):
        existing.best_s2_lap = best_s2_lap
        changed = True
    if best_s3_lap != (existing.best_s3_lap or 0):
        existing.best_s3_lap = best_s3_lap
        changed = True
    if changed:
        existing.laps = merged_laps
    return changed


def _effective_lap_time(lap_number: int, lap_time_ms: int | None, history_row: RaceSessionHistory | dict | None) -> int | None:
    direct = _positive_lap_time(lap_time_ms)
    if direct is not None:
        return direct
    history = _serialize_history_row(history_row)
    if not history:
        return None
    lap = _history_laps_by_number(history.get("laps")).get(int(lap_number or 0))
    if not lap:
        return None
    return _positive_lap_time(lap.get("lap_time_ms"))


async def _get_session_history_row(db: AsyncSession, race_id: int, vehicle_index: int) -> RaceSessionHistory | None:
    row = await db.execute(
        select(RaceSessionHistory).where(
            RaceSessionHistory.race_id == race_id,
            RaceSessionHistory.vehicle_index == vehicle_index,
        )
    )
    return row.scalars().first()


async def _backfill_telemetry_lap_times(db: AsyncSession, race_id: int, vehicle_index: int, laps: list[dict]) -> int:
    lap_times = {
        lap_number: _positive_lap_time(lap.get("lap_time_ms"))
        for lap_number, lap in _history_laps_by_number(laps).items()
    }
    if not lap_times:
        return 0

    rows = await db.execute(
        select(LapTelemetry).where(
            LapTelemetry.race_id == race_id,
            LapTelemetry.vehicle_index == vehicle_index,
        )
    )
    updated = 0
    for row in rows.scalars().all():
        replacement = lap_times.get(row.lap_number)
        if replacement is None:
            continue
        if _positive_lap_time(row.lap_time_ms) is None:
            row.lap_time_ms = replacement
            updated += 1
    return updated


def _lap_response(race_id: int, vehicle_index: int, telemetry: LapTelemetry, history_row: RaceSessionHistory | dict | None = None) -> dict:
    return {
        "race_id": race_id,
        "vehicle_index": vehicle_index,
        "lap_number": telemetry.lap_number,
        "lap_time_ms": _effective_lap_time(telemetry.lap_number, telemetry.lap_time_ms, history_row),
        "samples": telemetry.samples,
    }


async def _select_best_lap(db: AsyncSession, race_id: int, vehicle_index: int, history_row: RaceSessionHistory | None = None) -> tuple[LapTelemetry | None, int | None]:
    rows = await db.execute(
        select(LapTelemetry).where(
            LapTelemetry.race_id == race_id,
            LapTelemetry.vehicle_index == vehicle_index,
        ).order_by(LapTelemetry.lap_number)
    )
    laps = rows.scalars().all()
    if not laps:
        return None, None
    if history_row is None:
        history_row = await _get_session_history_row(db, race_id, vehicle_index)

    best_row: LapTelemetry | None = None
    best_time: int | None = None
    fallback_row: LapTelemetry | None = None

    for lap in laps:
        if lap.samples and fallback_row is None:
            fallback_row = lap
        effective_time = _effective_lap_time(lap.lap_number, lap.lap_time_ms, history_row)
        if effective_time is None:
            continue
        if best_time is None or effective_time < best_time:
            best_row = lap
            best_time = effective_time

    if best_row is not None:
        return best_row, best_time
    return fallback_row, None


async def _upsert_session_history_rows(db: AsyncSession, payload: SessionHistorySubmit) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    backfilled = 0

    for vehicle_history in payload.vehicles:
        if not vehicle_history.laps:
            continue

        existing = await _get_session_history_row(db, payload.race_id, vehicle_history.vehicle_index)
        if existing:
            if _merge_history_row(existing, vehicle_history):
                updated += 1
            history_row = existing
        else:
            history_row = RaceSessionHistory(
                race_id=payload.race_id,
                vehicle_index=vehicle_history.vehicle_index,
                best_lap_num=vehicle_history.best_lap_num,
                best_s1_lap=vehicle_history.best_s1_lap,
                best_s2_lap=vehicle_history.best_s2_lap,
                best_s3_lap=vehicle_history.best_s3_lap,
                laps=[_model_dump(lap) for lap in vehicle_history.laps],
            )
            db.add(history_row)
            inserted += 1

        backfilled += await _backfill_telemetry_lap_times(
            db,
            payload.race_id,
            vehicle_history.vehicle_index,
            [_model_dump(lap) for lap in vehicle_history.laps],
        )

    return inserted, updated, backfilled


# ---------------------------------------------------------------------------
# POST /submit
# ---------------------------------------------------------------------------

@router.post("/submit")
async def submit_telemetry(payload: LapSubmit, db: AsyncSession = Depends(get_db), _: bool = Depends(verify_agent_token)):
    if not payload.samples:
        return {"status": "skipped", "reason": "empty samples"}

    history_row = await _get_session_history_row(db, payload.race_id, payload.vehicle_index)
    effective_lap_time = _effective_lap_time(payload.lap_number, payload.lap_time_ms, history_row)
    samples = [_model_dump(sample) for sample in payload.samples]

    existing = await db.execute(
        select(LapTelemetry).where(
            LapTelemetry.race_id       == payload.race_id,
            LapTelemetry.vehicle_index == payload.vehicle_index,
            LapTelemetry.lap_number    == payload.lap_number,
        )
    )
    current = existing.scalars().first()
    if current:
        changed = False
        if effective_lap_time is not None and _positive_lap_time(current.lap_time_ms) is None:
            current.lap_time_ms = effective_lap_time
            changed = True
        if len(samples) > len(current.samples or []):
            current.samples = samples
            changed = True
        if changed:
            await db.commit()
            return {"status": "updated", "samples": len(current.samples or []), "lap_time_ms": current.lap_time_ms}
        return {"status": "duplicate", "samples": len(current.samples or []), "lap_time_ms": _effective_lap_time(current.lap_number, current.lap_time_ms, history_row)}

    lt = LapTelemetry(
        race_id       = payload.race_id,
        vehicle_index = payload.vehicle_index,
        lap_number    = payload.lap_number,
        lap_time_ms   = effective_lap_time,
        samples       = samples,
    )
    db.add(lt)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.execute(
            select(LapTelemetry).where(
                LapTelemetry.race_id == payload.race_id,
                LapTelemetry.vehicle_index == payload.vehicle_index,
                LapTelemetry.lap_number == payload.lap_number,
            )
        )
        current = existing.scalars().first()
        if not current:
            raise
        changed = False
        if effective_lap_time is not None and _positive_lap_time(current.lap_time_ms) is None:
            current.lap_time_ms = effective_lap_time
            changed = True
        if len(samples) > len(current.samples or []):
            current.samples = samples
            changed = True
        if changed:
            await db.commit()
            return {"status": "updated", "samples": len(current.samples or []), "lap_time_ms": current.lap_time_ms}
        return {"status": "duplicate", "samples": len(current.samples or []), "lap_time_ms": _effective_lap_time(current.lap_number, current.lap_time_ms, history_row)}

    return {"status": "ok", "samples": len(payload.samples), "lap_time_ms": effective_lap_time}


# ---------------------------------------------------------------------------
# POST /session-history — приём секторных времён от агента
# ---------------------------------------------------------------------------

@router.post("/session-history")
async def submit_session_history(payload: SessionHistorySubmit, db: AsyncSession = Depends(get_db), _: bool = Depends(verify_agent_token)):
    try:
        inserted, updated, backfilled = await _upsert_session_history_rows(db, payload)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        inserted, updated, backfilled = await _upsert_session_history_rows(db, payload)
        await db.commit()

    return {
        "status": "ok",
        "vehicles_stored": inserted,
        "vehicles_updated": updated,
        "laps_backfilled": backfilled,
    }


@router.get("/{race_id}/session-history")
async def get_session_history_overview(race_id: int, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(RaceSessionHistory).where(RaceSessionHistory.race_id == race_id).order_by(RaceSessionHistory.vehicle_index)
    )
    histories = rows.scalars().all()

    results_res = await db.execute(select(RaceResult).where(RaceResult.race_id == race_id))
    results_map = {result.vehicle_index: result for result in results_res.scalars().all()}

    return [
        {
            **(_serialize_history_row(history) or {}),
            "driver_name": results_map[history.vehicle_index].driver_name if history.vehicle_index in results_map else f"Car {history.vehicle_index}",
            "team_color": _get_team_color(results_map[history.vehicle_index].team_id if history.vehicle_index in results_map else -1),
            "is_human": results_map[history.vehicle_index].is_human if history.vehicle_index in results_map else False,
        }
        for history in histories
    ]


@router.get("/{race_id}/{vehicle_index}/session-history")
async def get_vehicle_session_history(race_id: int, vehicle_index: int, db: AsyncSession = Depends(get_db)):
    history = await _get_session_history_row(db, race_id, vehicle_index)
    if not history:
        raise HTTPException(404, "Session history not found")

    result_row = await db.execute(
        select(RaceResult).where(
            RaceResult.race_id == race_id,
            RaceResult.vehicle_index == vehicle_index,
        )
    )
    result = result_row.scalars().first()
    payload = _serialize_history_row(history) or {}
    payload.update(
        {
            "driver_name": result.driver_name if result else f"Car {vehicle_index}",
            "team_color": _get_team_color(result.team_id if result else -1),
            "is_human": result.is_human if result else False,
        }
    )
    return payload


# ---------------------------------------------------------------------------
# GET /{race_id} — обзор: какие круги есть по каким пилотам
# ---------------------------------------------------------------------------

@router.get("/{race_id}")
async def get_overview(race_id: int, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(
            LapTelemetry
        ).where(LapTelemetry.race_id == race_id)
        .order_by(LapTelemetry.vehicle_index, LapTelemetry.lap_number)
    )
    telemetry_rows = rows.scalars().all()

    histories_res = await db.execute(
        select(RaceSessionHistory).where(RaceSessionHistory.race_id == race_id)
    )
    histories = {history.vehicle_index: history for history in histories_res.scalars().all()}

    by_vidx: dict[int, list] = {}
    for telemetry in telemetry_rows:
        by_vidx.setdefault(telemetry.vehicle_index, []).append(
            {
                "lap": telemetry.lap_number,
                "lap_ms": _effective_lap_time(telemetry.lap_number, telemetry.lap_time_ms, histories.get(telemetry.vehicle_index)),
            }
        )

    results_res = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id)
    )
    results_map = {r.vehicle_index: r for r in results_res.scalars().all()}

    return [
        {
            "vehicle_index": vidx,
            "driver_name":   results_map[vidx].driver_name if vidx in results_map else f"Car {vidx}",
            "team_color":    _get_team_color(results_map[vidx].team_id if vidx in results_map else -1),
            "is_human":      results_map[vidx].is_human if vidx in results_map else False,
            "laps":          laps,
        }
        for vidx, laps in sorted(by_vidx.items())
    ]


# ---------------------------------------------------------------------------
# GET /{race_id}/{vidx}/{lap} — данные конкретного круга
# ---------------------------------------------------------------------------

@router.get("/{race_id}/{vehicle_index}/{lap_number:int}")
async def get_lap(race_id: int, vehicle_index: int, lap_number: int,
                  db: AsyncSession = Depends(get_db)):
    row = await db.execute(
        select(LapTelemetry).where(
            LapTelemetry.race_id       == race_id,
            LapTelemetry.vehicle_index == vehicle_index,
            LapTelemetry.lap_number    == lap_number,
        )
    )
    lt = row.scalars().first()
    if not lt:
        raise HTTPException(404, "Lap telemetry not found")
    history_row = await _get_session_history_row(db, race_id, vehicle_index)
    return _lap_response(race_id, vehicle_index, lt, history_row)


# ---------------------------------------------------------------------------
# GET /{race_id}/{vidx}/best — лучший круг пилота
# ---------------------------------------------------------------------------

@router.get("/{race_id}/{vehicle_index}/best")
async def get_best_lap(race_id: int, vehicle_index: int, db: AsyncSession = Depends(get_db)):
    history_row = await _get_session_history_row(db, race_id, vehicle_index)
    best, best_time = await _select_best_lap(db, race_id, vehicle_index, history_row)
    if not best:
        raise HTTPException(404, "No lap telemetry found")
    payload = _lap_response(race_id, vehicle_index, best, history_row)
    payload["lap_time_ms"] = best_time
    return payload


# ---------------------------------------------------------------------------
# GET /{race_id}/compare?a=0&b=1 — сравнение двух пилотов (лучшие круги)
# ---------------------------------------------------------------------------

@router.get("/{race_id}/compare")
async def compare_laps(race_id: int, a: int = 0, b: int = 1,
                       db: AsyncSession = Depends(get_db)):
    history_a = await _get_session_history_row(db, race_id, a)
    history_b = await _get_session_history_row(db, race_id, b)
    lap_a, lap_a_time = await _select_best_lap(db, race_id, a, history_a)
    lap_b, lap_b_time = await _select_best_lap(db, race_id, b, history_b)

    if not lap_a or not lap_b:
        raise HTTPException(404, "Not enough lap data for comparison")

    results_res = await db.execute(
        select(RaceResult).where(
            RaceResult.race_id.in_([race_id]),
            RaceResult.vehicle_index.in_([a, b]),
        )
    )
    names = {r.vehicle_index: (r.driver_name, _get_team_color(r.team_id))
             for r in results_res.scalars().all()}

    def _build(vidx, lt, lap_time_ms, history_row):
        name, color = names.get(vidx, (f"Car {vidx}", "#888"))
        payload = _lap_response(race_id, vidx, lt, history_row)
        payload.update(
            {
                "driver_name": name,
                "team_color": color,
                "lap_time_ms": lap_time_ms,
            }
        )
        return payload

    return {
        "a": _build(a, lap_a, lap_a_time, history_a),
        "b": _build(b, lap_b, lap_b_time, history_b),
    }


# ---------------------------------------------------------------------------
# GET /race/{race_id}/analysis — full race analysis data
# ---------------------------------------------------------------------------

@router.get("/race-analysis/{race_id}")
async def race_analysis(race_id: int, db: AsyncSession = Depends(get_db)):
    """
    Returns comprehensive race analysis:
    - Lap times per driver (with compound info)
    - Sector times matrix
    - Position per lap (from session history)
    - Theoretical best laps
    - Tyre strategy timeline
    """
    # 1. Race info
    race_row = await db.execute(select(Race).where(Race.id == race_id))
    race = race_row.scalars().first()
    if not race:
        raise HTTPException(404, "Race not found")

    # 2. Results
    res_rows = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id).order_by(RaceResult.position)
    )
    results = res_rows.scalars().all()
    results_map = {r.vehicle_index: r for r in results}

    # 3. Session history (sector times)
    sh_rows = await db.execute(
        select(RaceSessionHistory).where(RaceSessionHistory.race_id == race_id)
    )
    session_histories = {sh.vehicle_index: sh for sh in sh_rows.scalars().all()}

    # Build driver list with lap times and sectors
    drivers = []
    for r in results:
        vidx = r.vehicle_index
        sh = session_histories.get(vidx)

        lap_data = []
        best_s1 = best_s2 = best_s3 = None
        theoretical_best_ms = None

        if sh and sh.laps:
            for lap in sh.laps:
                lap_data.append({
                    "lap": lap["lap_number"],
                    "time_ms": lap["lap_time_ms"],
                    "s1_ms": lap["sector1_ms"],
                    "s2_ms": lap["sector2_ms"],
                    "s3_ms": lap["sector3_ms"],
                    "valid": lap.get("lap_valid", True),
                })

            # Calculate theoretical best
            valid_laps = [l for l in sh.laps if l.get("lap_valid", True) and l["lap_time_ms"] > 0]
            if valid_laps:
                s1_times = [l["sector1_ms"] for l in valid_laps if l["sector1_ms"] > 0]
                s2_times = [l["sector2_ms"] for l in valid_laps if l["sector2_ms"] > 0]
                s3_times = [l["sector3_ms"] for l in valid_laps if l["sector3_ms"] > 0]
                if s1_times and s2_times and s3_times:
                    best_s1 = min(s1_times)
                    best_s2 = min(s2_times)
                    best_s3 = min(s3_times)
                    theoretical_best_ms = best_s1 + best_s2 + best_s3

        drivers.append({
            "vehicle_index": vidx,
            "driver_name": r.driver_name,
            "team_name": r.team_name,
            "team_color": _get_team_color(r.team_id),
            "is_human": r.is_human,
            "position": r.position,
            "grid_position": r.grid_position,
            "best_lap_ms": r.best_lap_ms,
            "theoretical_best_ms": theoretical_best_ms,
            "best_sectors": {"s1": best_s1, "s2": best_s2, "s3": best_s3},
            "tyre_stints": r.tyre_stints or [],
            "num_pit_stops": r.num_pit_stops or 0,
            "result_status": r.result_status,
            "points": r.points,
            "laps": lap_data,
        })

    return {
        "race_id": race_id,
        "track_name": race.track_name,
        "total_laps": race.total_laps,
        "weather_start": race.weather_start,
        "weather_end": race.weather_end,
        "drivers": drivers,
    }


# ---------------------------------------------------------------------------
# GET /braking-analysis/{race_id} — braking zone analysis
# ---------------------------------------------------------------------------

@router.get("/braking-analysis/{race_id}")
async def braking_analysis(race_id: int, db: AsyncSession = Depends(get_db)):
    """Braking zone analysis for human drivers' best laps."""
    # Get human drivers
    res_rows = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id, RaceResult.is_human == True)
    )
    results = res_rows.scalars().all()

    drivers = []
    for r in results:
        history_row = await _get_session_history_row(db, race_id, r.vehicle_index)
        best, best_time = await _select_best_lap(db, race_id, r.vehicle_index, history_row)
        if not best or not best.samples:
            continue

        samples = best.samples
        zones = []
        i = 0
        while i < len(samples):
            # Find brake zone start
            if samples[i].get("brk", 0) > 0.1:
                zone_start = i
                peak_brake = 0
                while i < len(samples) and samples[i].get("brk", 0) > 0.05:
                    peak_brake = max(peak_brake, samples[i].get("brk", 0))
                    i += 1
                zone_end = i
                if zone_end - zone_start >= 3:
                    entry_spd = samples[zone_start].get("spd", 0)
                    exit_spd = samples[min(zone_end, len(samples)-1)].get("spd", 0)
                    min_spd = min(s.get("spd", 999) for s in samples[zone_start:zone_end])
                    dist_start = samples[zone_start].get("dist", 0)
                    dist_end = samples[min(zone_end, len(samples)-1)].get("dist", 0)
                    zones.append({
                        "distance": round(dist_start, 1),
                        "distance_end": round(dist_end, 1),
                        "braking_distance": round(dist_end - dist_start, 1),
                        "peak_brake": round(peak_brake, 3),
                        "entry_speed": entry_spd,
                        "exit_speed": exit_spd,
                        "min_speed": min_spd,
                        "trail_braking": any(
                            0.05 < samples[j].get("brk", 0) < 0.5 and samples[j].get("thr", 0) > 0.1
                            for j in range(max(zone_start, zone_end - 5), zone_end)
                        ),
                    })
            else:
                i += 1

        drivers.append({
            "vehicle_index": r.vehicle_index,
            "driver_name": r.driver_name,
            "team_color": _get_team_color(r.team_id),
            "lap_number": best.lap_number,
            "lap_time_ms": best_time,
            "zones": zones,
        })

    return {"race_id": race_id, "drivers": drivers}


# ---------------------------------------------------------------------------
# GET /throttle-analysis/{race_id} — throttle usage analysis
# ---------------------------------------------------------------------------

@router.get("/throttle-analysis/{race_id}")
async def throttle_analysis(race_id: int, db: AsyncSession = Depends(get_db)):
    """Throttle usage analysis for human drivers' best laps."""
    res_rows = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id, RaceResult.is_human == True)
    )
    results = res_rows.scalars().all()

    drivers = []
    for r in results:
        history_row = await _get_session_history_row(db, race_id, r.vehicle_index)
        best, best_time = await _select_best_lap(db, race_id, r.vehicle_index, history_row)
        if not best or not best.samples:
            continue

        samples = best.samples
        total = len(samples)
        if total == 0:
            continue

        full_throttle = sum(1 for s in samples if s.get("thr", 0) >= 0.95)
        zero_throttle = sum(1 for s in samples if s.get("thr", 0) < 0.05)
        partial_throttle = total - full_throttle - zero_throttle

        # Smoothness: average absolute difference between consecutive throttle values
        thr_values = [s.get("thr", 0) for s in samples]
        smoothness = 0
        if len(thr_values) > 1:
            diffs = [abs(thr_values[j+1] - thr_values[j]) for j in range(len(thr_values)-1)]
            smoothness = round(1.0 - min(sum(diffs) / len(diffs) * 10, 1.0), 3)  # 0=rough, 1=smooth

        # Coast (neither full throttle nor braking)
        coasting = sum(1 for s in samples if 0.05 <= s.get("thr", 0) < 0.95 and s.get("brk", 0) < 0.05)

        # DRS usage
        drs_samples = sum(1 for s in samples if s.get("drs", 0) == 1)

        drivers.append({
            "vehicle_index": r.vehicle_index,
            "driver_name": r.driver_name,
            "team_color": _get_team_color(r.team_id),
            "lap_number": best.lap_number,
            "lap_time_ms": best_time,
            "total_samples": total,
            "full_throttle_pct": round(full_throttle / total * 100, 1),
            "zero_throttle_pct": round(zero_throttle / total * 100, 1),
            "partial_throttle_pct": round(partial_throttle / total * 100, 1),
            "coasting_pct": round(coasting / total * 100, 1),
            "smoothness": smoothness,
            "drs_pct": round(drs_samples / total * 100, 1),
            "max_speed": max((s.get("spd", 0) for s in samples), default=0),
            "avg_speed": round(sum(s.get("spd", 0) for s in samples) / total, 1),
        })

    return {"race_id": race_id, "drivers": drivers}


# ---------------------------------------------------------------------------
# POST /race-analysis/{race_id}/debrief — AI race debrief
# ---------------------------------------------------------------------------

@router.post("/race-analysis/{race_id}/debrief")
async def race_debrief(
    race_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """AI race debrief with corner-specific telemetry analysis."""
    import os, httpx

    # `web_user_id` field name preserved for back-compat with old launcher/agent
    # builds; treated as users.id (with fallback to legacy_web_user_id lookup).
    requested_user_id = body.get("web_user_id") or body.get("user_id")
    if not requested_user_id:
        raise HTTPException(400, "user_id required")

    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_url = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    if not groq_key:
        return {"debrief": "Race engineer unavailable — GROQ_API_KEY not set."}

    from sqlalchemy import or_
    user_row = await db.execute(
        select(User).where(or_(User.id == requested_user_id, User.legacy_web_user_id == requested_user_id))
    )
    user_record = user_row.scalars().first()
    player_id = user_record.id if user_record else None

    # Get race info
    race_row = await db.execute(select(Race).where(Race.id == race_id))
    race = race_row.scalars().first()
    if not race:
        raise HTTPException(404, "Race not found")

    # Get all results
    res_rows = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id).order_by(RaceResult.position)
    )
    results = res_rows.scalars().all()

    # Get session history for sectors
    sh_rows = await db.execute(
        select(RaceSessionHistory).where(RaceSessionHistory.race_id == race_id)
    )
    histories = {sh.vehicle_index: sh for sh in sh_rows.scalars().all()}

    # Build context
    context_parts = [f"Race: {race.track_name}, {race.total_laps} laps"]

    # Race results summary
    for r in results[:10]:
        sh = histories.get(r.vehicle_index)
        best_s1 = best_s2 = best_s3 = "?"
        if sh and sh.laps:
            valid = [l for l in sh.laps if l.get("lap_valid", True) and l["lap_time_ms"] > 0]
            if valid:
                s1s = [l["sector1_ms"] for l in valid if l["sector1_ms"] > 0]
                s2s = [l["sector2_ms"] for l in valid if l["sector2_ms"] > 0]
                s3s = [l["sector3_ms"] for l in valid if l["sector3_ms"] > 0]
                if s1s: best_s1 = f"{min(s1s)/1000:.3f}"
                if s2s: best_s2 = f"{min(s2s)/1000:.3f}"
                if s3s: best_s3 = f"{min(s3s)/1000:.3f}"

        marker = " ← THIS DRIVER" if r.user_id == player_id and player_id else ""
        context_parts.append(
            f"P{r.position} {r.driver_name} ({r.team_name}) - Best: {r.best_lap_ms}ms, "
            f"Sectors: {best_s1}/{best_s2}/{best_s3}, Pits: {r.num_pit_stops}, "
            f"Grid: {r.grid_position}{marker}"
        )

    context = "\n".join(context_parts)

    system_prompt = (
        "Ты — элитный гоночный инженер Формулы-1, уровня Питера 'Бонно' Боннингтона. "
        "Тебе дают данные реальной гонки. Проведи детальный дебриф:\n\n"
        "1. ОБЩАЯ ОЦЕНКА — как прошла гонка для пилота (2-3 предложения)\n"
        "2. СЕКТОРНЫЙ АНАЛИЗ — где пилот силён, где теряет. Конкретные числа.\n"
        "3. ЧТО УЛУЧШИТЬ — 3 конкретных совета с цифрами (напр. 'В секторе 2 ты теряешь 0.3с "
        "по сравнению с лидером — работай над поздним торможением в T5-T6')\n"
        "4. СТРАТЕГИЯ — была ли оптимальной, что можно было сделать иначе\n"
        "5. ПОЗИТИВ — что пилот сделал хорошо\n\n"
        "Используй язык, на котором написан вопрос (русский/английский). "
        "Будь конкретен, используй числа из данных. Формат: Markdown."
    )

    question = body.get("question", "Проведи полный дебриф моей гонки")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                groq_url,
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": groq_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Данные гонки:\n{context}\n\nВопрос: {question}"},
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.7,
                },
            )
            r.raise_for_status()
            data = r.json()
            return {"debrief": data["choices"][0]["message"]["content"]}
    except Exception as e:
        print(f"[DEBRIEF] Error: {e}")
        return {"debrief": "Связь потеряна — инженер временно недоступен."}


# ---------------------------------------------------------------------------
# GET /weather-correlation/{race_id} — weather impact on lap times
# ---------------------------------------------------------------------------

@router.get("/weather-correlation/{race_id}")
async def weather_correlation(race_id: int, db: AsyncSession = Depends(get_db)):
    """Analyze weather impact on lap times."""
    race_row = await db.execute(select(Race).where(Race.id == race_id))
    race = race_row.scalars().first()
    if not race:
        raise HTTPException(404, "Race not found")

    sh_rows = await db.execute(
        select(RaceSessionHistory).where(RaceSessionHistory.race_id == race_id)
    )
    histories = {sh.vehicle_index: sh for sh in sh_rows.scalars().all()}

    res_rows = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id, RaceResult.is_human == True)
    )
    results = res_rows.scalars().all()

    WEATHER_NAMES = {0: "Clear", 1: "Light Cloud", 2: "Overcast", 3: "Light Rain", 4: "Heavy Rain", 5: "Storm"}

    drivers = []
    for r in results:
        sh = histories.get(r.vehicle_index)
        if not sh or not sh.laps:
            continue
        valid_laps = [l for l in sh.laps if l.get("lap_valid", True) and l["lap_time_ms"] > 0]
        if not valid_laps:
            continue
        lap_times = [l["lap_time_ms"] for l in valid_laps]
        avg_time = sum(lap_times) / len(lap_times)
        mid = len(valid_laps) // 2
        first_half_avg = sum(l["lap_time_ms"] for l in valid_laps[:mid]) / max(mid, 1)
        second_half_avg = sum(l["lap_time_ms"] for l in valid_laps[mid:]) / max(len(valid_laps) - mid, 1)

        drivers.append({
            "vehicle_index": r.vehicle_index,
            "driver_name": r.driver_name,
            "team_color": _get_team_color(r.team_id),
            "avg_lap_ms": round(avg_time),
            "best_lap_ms": min(lap_times),
            "worst_lap_ms": max(lap_times),
            "consistency_ms": round(max(lap_times) - min(lap_times)),
            "first_half_avg_ms": round(first_half_avg),
            "second_half_avg_ms": round(second_half_avg),
            "pace_change_ms": round(second_half_avg - first_half_avg),
            "total_valid_laps": len(valid_laps),
        })

    return {
        "race_id": race_id,
        "track_name": race.track_name,
        "weather_start": WEATHER_NAMES.get(race.weather_start, "Unknown"),
        "weather_start_id": race.weather_start,
        "weather_end": WEATHER_NAMES.get(race.weather_end, "Unknown"),
        "weather_end_id": race.weather_end,
        "weather_changed": race.weather_start != race.weather_end,
        "air_temp": race.air_temp,
        "track_temp": race.track_temp,
        "drivers": drivers,
    }


# ---------------------------------------------------------------------------
# GET /corner-analysis/{race_id}/{vehicle_index} — corner-by-corner analysis
# ---------------------------------------------------------------------------

@router.get("/corner-analysis/{race_id}/{vehicle_index}")
async def corner_analysis(race_id: int, vehicle_index: int, db: AsyncSession = Depends(get_db)):
    """Corner-by-corner analysis from best lap telemetry."""
    history_row = await _get_session_history_row(db, race_id, vehicle_index)
    best, best_time = await _select_best_lap(db, race_id, vehicle_index, history_row)
    if not best or not best.samples:
        raise HTTPException(404, "No telemetry data")

    res_row = await db.execute(
        select(RaceResult).where(
            RaceResult.race_id == race_id,
            RaceResult.vehicle_index == vehicle_index,
        )
    )
    result = res_row.scalars().first()
    driver_name = result.driver_name if result else f"Car {vehicle_index}"
    team_color = _get_team_color(result.team_id) if result else "#888"

    samples = best.samples
    corners = []
    i = 0
    corner_num = 0

    while i < len(samples):
        brk = samples[i].get("brk", 0)
        if brk > 0.2:
            corner_num += 1
            brake_start = i
            entry_speed = samples[i].get("spd", 0)
            entry_dist = samples[i].get("dist", 0)
            peak_brake = brk

            while i < len(samples) and samples[i].get("brk", 0) > 0.05:
                peak_brake = max(peak_brake, samples[i].get("brk", 0))
                i += 1

            apex_zone_end = min(i + 20, len(samples))
            min_speed = 999
            apex_idx = i
            for j in range(max(brake_start, i - 10), apex_zone_end):
                spd = samples[j].get("spd", 999)
                if spd < min_speed:
                    min_speed = spd
                    apex_idx = j

            exit_idx = apex_idx
            while exit_idx < min(apex_idx + 30, len(samples)):
                if samples[exit_idx].get("thr", 0) > 0.8:
                    break
                exit_idx += 1

            exit_speed = samples[min(exit_idx, len(samples) - 1)].get("spd", 0)
            exit_dist = samples[min(exit_idx, len(samples) - 1)].get("dist", 0)
            apex_gear = samples[min(apex_idx, len(samples) - 1)].get("gear", 0)
            t_entry = samples[brake_start].get("t", 0)
            t_exit = samples[min(exit_idx, len(samples) - 1)].get("t", 0)
            corner_time_ms = round((t_exit - t_entry) * 1000) if t_exit > t_entry else 0

            trail_braking = any(
                samples[j].get("brk", 0) > 0.05 and samples[j].get("thr", 0) > 0.1
                for j in range(max(brake_start, apex_idx - 5), min(apex_idx + 1, len(samples)))
            )

            if entry_speed - min_speed > 20:
                corners.append({
                    "corner": corner_num,
                    "distance": round(entry_dist),
                    "entry_speed": entry_speed,
                    "apex_speed": min_speed,
                    "exit_speed": exit_speed,
                    "speed_loss": entry_speed - min_speed,
                    "apex_gear": apex_gear,
                    "peak_brake": round(peak_brake, 2),
                    "braking_distance": round(exit_dist - entry_dist),
                    "corner_time_ms": corner_time_ms,
                    "trail_braking": trail_braking,
                })
        else:
            i += 1

    return {
        "race_id": race_id,
        "vehicle_index": vehicle_index,
        "driver_name": driver_name,
        "team_color": team_color,
        "lap_number": best.lap_number,
        "lap_time_ms": best_time,
        "corners": corners,
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_team_color(team_id: int) -> str:
    from shared.f1_mappings import get_team
    return get_team(team_id).get("color", "#888888")
