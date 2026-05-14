"""
GET /api/achievements/{season_id}  — все разблокированные ачивки сезона
GET /api/records/{season_id}       — рекорды трасс (fastest lap)
GET /api/fun_stats/{season_id}     — fun stats (on-demand)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.base import get_db
from backend.models.models import (
    PlayerAchievement, Achievement, Player, RaceResult, Race
)

router = APIRouter(prefix="/api", tags=["achievements"])


@router.get("/achievements/{season_id}")
async def get_achievements(season_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(
            PlayerAchievement,
            Achievement.name.label("ach_name"),
            Achievement.icon.label("ach_icon"),
            Achievement.description.label("ach_desc"),
            Player.name.label("player_name"),
        )
        .join(Achievement, Achievement.id == PlayerAchievement.achievement_id)
        .join(Player, Player.id == PlayerAchievement.player_id)
        .join(Race, Race.id == PlayerAchievement.race_id, isouter=True)
        .where(Race.season_id == season_id)
        .order_by(PlayerAchievement.unlocked_at.desc())
    )
    rows = res.all()
    return [
        {
            "player_name": r.player_name,
            "ach_name":    r.ach_name,
            "ach_icon":    r.ach_icon,
            "ach_desc":    r.ach_desc,
            "unlocked_at": r.PlayerAchievement.unlocked_at,
        }
        for r in rows
    ]


@router.get("/records/{season_id}")
async def get_track_records(season_id: int, db: AsyncSession = Depends(get_db)):
    """Абсолютный fastest lap на каждой трассе за сезон."""
    races_res = await db.execute(
        select(Race).where(Race.season_id == season_id)
    )
    races = {r.id: r for r in races_res.scalars().all()}

    if not races:
        return []

    # Лучший FL для каждого track_id
    records: dict[int, dict] = {}
    fl_res = await db.execute(
        select(RaceResult, Player.name.label("player_name"))
        .join(Player, Player.id == RaceResult.player_id, isouter=True)
        .where(
            RaceResult.race_id.in_(list(races.keys())),
            RaceResult.has_fastest_lap == True,  # noqa: E712
            RaceResult.best_lap_ms != None,       # noqa: E711
        )
    )
    for rr, pname in fl_res.all():
        race = races.get(rr.race_id)
        if not race:
            continue
        tid = race.track_id
        if tid not in records or rr.best_lap_ms < records[tid]["best_lap_ms"]:
            records[tid] = {
                "track_id":    tid,
                "track_name":  race.track_name,
                "best_lap_ms": rr.best_lap_ms,
                "driver_name": rr.driver_name,
                "player_name": pname,
                "race_id":     rr.race_id,
            }

    return sorted(records.values(), key=lambda r: r["track_name"])


@router.get("/fun_stats/{season_id}")
async def get_fun_stats(season_id: int):
    from backend.services.fun_stats import compute_fun_stats
    stats = await compute_fun_stats(season_id)
    return stats or []
