"""
GET /api/standings/{season_id}    — WDC
GET /api/constructors/{season_id} — WCC
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.base import get_db
from backend.models.models import ChampionshipStanding, ConstructorStanding
from shared.f1_mappings import get_team_color

router = APIRouter(prefix="/api", tags=["standings"])


@router.get("/standings/{season_id}")
async def get_standings(season_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ChampionshipStanding)
        .where(ChampionshipStanding.season_id == season_id)
        .order_by(ChampionshipStanding.total_points.desc())
    )
    standings = res.scalars().all()

    return [
        {
            "position":     i + 1,
            "driver_id":    s.driver_id,
            "driver_name":  s.driver_name,
            "team_id":      s.team_id,
            "team_name":    s.team_name,
            "team_color":   get_team_color(s.team_id),
            "player_id":    s.player_id,
            "is_human":     s.is_human,
            "total_points": s.total_points,
            "wins":         s.wins,
            "podiums":      s.podiums,
            "fastest_laps": s.fastest_laps,
            "dnfs":         s.dnfs,
            "best_finish":  s.best_finish,
        }
        for i, s in enumerate(standings)
    ]


@router.get("/constructors/{season_id}")
async def get_constructors(season_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ConstructorStanding)
        .where(ConstructorStanding.season_id == season_id)
        .order_by(ConstructorStanding.total_points.desc())
    )
    standings = res.scalars().all()

    return [
        {
            "position":     i + 1,
            "team_id":      s.team_id,
            "team_name":    s.team_name,
            "team_color":   get_team_color(s.team_id),
            "total_points": s.total_points,
            "wins":         s.wins,
            "driver_1":     s.driver_1_name,
            "driver_2":     s.driver_2_name,
        }
        for i, s in enumerate(standings)
    ]
