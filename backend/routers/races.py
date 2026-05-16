"""
POST /api/race/submit  — приём результатов от agent
GET  /api/race/{race_id}     — результаты гонки
GET  /api/races/{season_id}  — список гонок сезона
"""
import inspect

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from backend.db.base import get_db
from backend.services.auth_dependencies import verify_agent_token
from backend.models.models import Race, RaceResult, RaceEvent, Season
from backend.services.player_mapper import resolve_participants
from backend.services.round_detector import detect_round
from backend.services.standings_service import recalc_standings
from backend.services.bot_notifier import notify_race_uploaded
from backend.services.achievement_engine import check_achievements_after_race
from backend.services.glicko2 import recalc_ratings_after_race
from shared.f1_mappings import get_track_name, get_team, get_driver, get_result_status_name
from shared.points_system import calc_points

router = APIRouter(prefix="/api", tags=["races"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TyreStint(BaseModel):
    compound: str
    laps: int


class ParticipantSubmit(BaseModel):
    vehicle_index:   int
    is_human:        bool
    steam_name:      str | None = None
    driver_id:       int
    team_id:         int
    grid_position:   int | None = None
    position:        int | None = None
    result_status:   int = 3
    total_race_time: float | None = None
    best_lap_ms:     int | None = None
    penalties_time:  int | None = None
    num_penalties:   int | None = None
    num_pit_stops:   int | None = None
    tyre_stints:     list[TyreStint] = []
    has_fastest_lap: bool = False


class EventSubmit(BaseModel):
    event_code:  str
    event_data:  dict = {}
    lap_number:  int | None = None
    session_time: float | None = None


class RaceSubmit(BaseModel):
    season_id:      int
    session_uid:    int
    packet_format:  int = 2025
    track_id:       int
    weather_start:  int | None = None
    weather_end:    int | None = None
    total_laps:     int | None = None
    air_temp:       int | None = None
    track_temp:     int | None = None
    host_steam_name: str | None = None
    participants:   list[ParticipantSubmit]
    events:         list[EventSubmit] = []


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


async def _load_existing_race_by_session_uid(db: AsyncSession, session_uid: int) -> Race | None:
    result = await db.execute(select(Race).where(Race.session_uid == session_uid))
    return result.scalars().first()


def _duplicate_response(existing_race: Race | None) -> dict:
    return {
        "status": "duplicate",
        "message": "Race with this session_uid already exists",
        "race_id": existing_race.id if existing_race else None,
        "round": existing_race.round_number if existing_race else None,
        "track": existing_race.track_name if existing_race else None,
    }


async def _resolve_integrity_duplicate(db: AsyncSession, session_uid: int) -> dict | None:
    await db.rollback()
    existing_race = await _load_existing_race_by_session_uid(db, session_uid)
    if existing_race:
        return _duplicate_response(existing_race)
    return None


async def _run_background_job(job_name: str, func, *args, **kwargs) -> None:
    try:
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        print(f"[RACE_BG] {job_name} failed: {exc}")


# ---------------------------------------------------------------------------
# POST /api/race/submit
# ---------------------------------------------------------------------------

@router.post("/race/submit")
async def submit_race(
    payload: RaceSubmit,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_agent_token),
):
    # 1. Дедупликация по session_uid
    existing_race = await _load_existing_race_by_session_uid(db, payload.session_uid)
    if existing_race:
        return _duplicate_response(existing_race)

    # 2. Определяем round_number
    round_number, rd_status = await detect_round(
        db, payload.season_id, payload.track_id, payload.session_uid
    )
    if rd_status == "duplicate":
        return _duplicate_response(await _load_existing_race_by_session_uid(db, payload.session_uid))
    if rd_status == "reconnect":
        # TODO: уведомить через WebSocket/бот — пока просто принимаем как новый
        round_number = round_number or 1
    if round_number is None:
        round_number = 1

    # 3. Маппинг steam_name → player_id для human участников
    participants_raw = [
        {"vehicle_index": p.vehicle_index, "m_aiControlled": 0 if p.is_human else 1, "m_name": p.steam_name or ""}
        for p in payload.participants if p.is_human
    ]
    player_map, unresolved = await resolve_participants(db, participants_raw)

    # 4. Создаём Race
    race = Race(
        season_id=payload.season_id,
        round_number=round_number,
        track_id=payload.track_id,
        track_name=get_track_name(payload.track_id),
        session_uid=payload.session_uid,
        packet_format=payload.packet_format,
        weather_start=payload.weather_start,
        weather_end=payload.weather_end,
        total_laps=payload.total_laps,
        air_temp=payload.air_temp,
        track_temp=payload.track_temp,
    )
    db.add(race)
    try:
        await db.flush()  # получаем race.id
    except IntegrityError:
        duplicate = await _resolve_integrity_duplicate(db, payload.session_uid)
        if duplicate:
            return duplicate
        raise

    # 5. Создаём RaceResult для каждого участника
    for p in payload.participants:
        team  = get_team(p.team_id)
        driver = get_driver(p.driver_id)
        pts   = calc_points(p.position or 0, p.has_fastest_lap, p.result_status)

        result = RaceResult(
            race_id=race.id,
            season_id=payload.season_id,
            vehicle_index=p.vehicle_index,
            is_human=p.is_human,
            user_id=player_map.get(p.vehicle_index) if p.is_human else None,
            driver_id=p.driver_id,
            driver_name=driver["name"],
            team_id=p.team_id,
            team_name=team["name"],
            grid_position=p.grid_position,
            position=p.position,
            points=pts,
            result_status=p.result_status,
            total_race_time=p.total_race_time,
            best_lap_ms=p.best_lap_ms,
            penalties_time=p.penalties_time,
            num_penalties=p.num_penalties,
            num_pit_stops=p.num_pit_stops,
            num_tyre_stints=len(p.tyre_stints),
            tyre_stints=[_model_dump(s) for s in p.tyre_stints],
            has_fastest_lap=p.has_fastest_lap,
        )
        db.add(result)

    # 6. Сохраняем Events
    for ev in payload.events:
        db.add(RaceEvent(
            race_id=race.id,
            event_code=ev.event_code,
            event_data=ev.event_data,
            lap_number=ev.lap_number,
            session_time=ev.session_time,
        ))

    try:
        await db.commit()
    except IntegrityError:
        duplicate = await _resolve_integrity_duplicate(db, payload.session_uid)
        if duplicate:
            return duplicate
        raise

    # 7. Фоновые задачи: standings → ratings → bot notify
    background_tasks.add_task(_run_background_job, "recalc_standings", recalc_standings, payload.season_id)
    background_tasks.add_task(_run_background_job, "update_ratings", _update_ratings, race.id)
    background_tasks.add_task(
        _run_background_job,
        "notify_race_uploaded",
        notify_race_uploaded,
        race.id,
        payload.season_id,
        unresolved,
    )

    return {
        "status": "ok",
        "race_id": race.id,
        "round": round_number,
        "track": race.track_name,
        "unresolved_players": unresolved,
    }


async def _update_ratings(race_id: int) -> None:
    try:
        await recalc_ratings_after_race(race_id)
    except Exception as e:
        print(f"[RATINGS] Error: {e}")


# ---------------------------------------------------------------------------
# GET /api/race/session/{session_uid}
# ---------------------------------------------------------------------------

@router.get("/race/session/{session_uid}")
async def get_race_by_session_uid(
    session_uid: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_agent_token),
):
    race = await _load_existing_race_by_session_uid(db, session_uid)
    if not race:
        raise HTTPException(404, "Race not found")

    return {
        "status": "ok",
        "race_id": race.id,
        "season_id": race.season_id,
        "session_uid": race.session_uid,
        "round": race.round_number,
        "track_id": race.track_id,
        "track_name": race.track_name,
        "raced_at": race.raced_at,
    }


# ---------------------------------------------------------------------------
# GET /api/race/{race_id}
# ---------------------------------------------------------------------------

@router.get("/race/{race_id}")
async def get_race(race_id: int, db: AsyncSession = Depends(get_db)):
    race_res = await db.execute(select(Race).where(Race.id == race_id))
    race = race_res.scalars().first()
    if not race:
        raise HTTPException(404, "Race not found")

    results_res = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id)
    )
    results = results_res.scalars().all()

    events_res = await db.execute(
        select(RaceEvent).where(RaceEvent.race_id == race_id)
    )
    events = events_res.scalars().all()

    return {
        "id":           race.id,
        "season_id":    race.season_id,
        "round":        race.round_number,
        "track_id":     race.track_id,
        "track_name":   race.track_name,
        "raced_at":     race.raced_at,
        "total_laps":   race.total_laps,
        "weather_start": race.weather_start,
        "weather_end":  race.weather_end,
        "results": [
            {
                "vehicle_index":   r.vehicle_index,
                "is_human":        r.is_human,
                "player_id":       r.user_id,
                "driver_id":       r.driver_id,
                "driver_name":     r.driver_name,
                "team_id":         r.team_id,
                "team_name":       r.team_name,
                "grid_position":   r.grid_position,
                "position":        r.position,
                "points":          r.points,
                "result_status":   get_result_status_name(r.result_status),
                "best_lap_ms":     r.best_lap_ms,
                "penalties_time":  r.penalties_time,
                "num_pit_stops":   r.num_pit_stops,
                "tyre_stints":     r.tyre_stints,
                "has_fastest_lap": r.has_fastest_lap,
            }
            for r in sorted(results, key=lambda x: x.position or 99)
        ],
        "events": [
            {"code": e.event_code, "data": e.event_data, "lap": e.lap_number}
            for e in events
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/races/{season_id}
# ---------------------------------------------------------------------------

@router.get("/races/{season_id}")
async def get_races(season_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Race).where(Race.season_id == season_id).order_by(Race.round_number)
    )
    races = res.scalars().all()
    return [
        {
            "id":           r.id,
            "round":        r.round_number,
            "track_id":     r.track_id,
            "track_name":   r.track_name,
            "raced_at":     r.raced_at,
            "total_laps":   r.total_laps,
        }
        for r in races
    ]
