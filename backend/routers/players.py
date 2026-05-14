"""
GET /api/player/{player_id}/stats — статистика игрока
GET /api/calendar/{season_id}     — расписание сезона
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.base import get_db
from backend.models.models import Player, Season, Race, RaceResult, SeasonContract, ChampionshipStanding
from shared.f1_mappings import get_track_name, get_team_color

router = APIRouter(prefix="/api", tags=["players"])


@router.get("/player/{player_id}/stats")
async def get_player_stats(player_id: int, db: AsyncSession = Depends(get_db)):
    player_res = await db.execute(select(Player).where(Player.id == player_id))
    player = player_res.scalars().first()
    if not player:
        raise HTTPException(404, "Player not found")

    results_res = await db.execute(
        select(RaceResult).where(RaceResult.player_id == player_id)
    )
    results = results_res.scalars().all()

    if not results:
        return {"player_id": player_id, "name": player.name, "races": 0}

    positions = [r.position for r in results if r.position]
    points_total = sum(r.points for r in results)
    wins    = sum(1 for r in results if r.position == 1)
    podiums = sum(1 for r in results if r.position and r.position <= 3)
    dnfs    = sum(1 for r in results if r.result_status in (4, 6))
    fl      = sum(1 for r in results if r.has_fastest_lap)
    avg_pos = round(sum(positions) / len(positions), 2) if positions else None

    # История результатов по гонкам
    races_res = await db.execute(
        select(Race).where(Race.id.in_([r.race_id for r in results])).order_by(Race.round_number)
    )
    races = {r.id: r for r in races_res.scalars().all()}

    race_history = [
        {
            "race_id":    r.race_id,
            "round":      races[r.race_id].round_number if r.race_id in races else None,
            "track_name": races[r.race_id].track_name if r.race_id in races else None,
            "position":   r.position,
            "points":     r.points,
            "driver_name": r.driver_name,
            "team_name":  r.team_name,
        }
        for r in sorted(results, key=lambda x: races.get(x.race_id, Race()).round_number or 0)
    ]

    return {
        "player_id":    player_id,
        "name":         player.name,
        "total_points": points_total,
        "races":        len(results),
        "wins":         wins,
        "podiums":      podiums,
        "dnfs":         dnfs,
        "fastest_laps": fl,
        "avg_position": avg_pos,
        "best_finish":  min(positions) if positions else None,
        "race_history": race_history,
    }


@router.get("/player/{player_id}/season-history")
async def get_player_season_history(player_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика игрока по каждому сезону из ChampionshipStanding."""
    res = await db.execute(
        select(ChampionshipStanding, Season.name.label("season_name"), Season.status.label("season_status"))
        .join(Season, ChampionshipStanding.season_id == Season.id)
        .where(ChampionshipStanding.player_id == player_id)
        .order_by(Season.id)
    )
    rows = res.all()
    return [
        {
            "season_id":   row.ChampionshipStanding.season_id,
            "season_name": row.season_name,
            "status":      row.season_status,
            "position":    row.ChampionshipStanding.position,
            "points":      row.ChampionshipStanding.total_points,
            "wins":        row.ChampionshipStanding.wins,
            "podiums":     row.ChampionshipStanding.podiums,
            "fastest_laps": row.ChampionshipStanding.fastest_laps,
            "dnfs":        row.ChampionshipStanding.dnfs,
        }
        for row in rows
    ]


@router.get("/calendar/{season_id}")
async def get_calendar(season_id: int, db: AsyncSession = Depends(get_db)):
    season_res = await db.execute(select(Season).where(Season.id == season_id))
    season = season_res.scalars().first()
    if not season:
        raise HTTPException(404, "Season not found")

    calendar: list[dict] = season.calendar or []

    # Пройденные гонки
    done_res = await db.execute(select(Race).where(Race.season_id == season_id))
    done_tracks = {r.track_id: r for r in done_res.scalars().all()}

    result = []
    for entry in calendar:
        tid = entry["track_id"]
        done_race = done_tracks.get(tid)
        result.append({
            "round":      entry["round"],
            "track_id":   tid,
            "track_name": entry.get("track_name") or get_track_name(tid),
            "completed":  done_race is not None,
            "race_id":    done_race.id if done_race else None,
            "raced_at":   done_race.raced_at if done_race else None,
        })

    return result
