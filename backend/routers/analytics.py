"""
Analytics endpoints:
- GET /api/player/{id}/trends           — position/points trends over races
- GET /api/player/{id}/h2h/{other_id}   — head-to-head comparison
- GET /api/player/{id}/tyre-stats       — tyre compound performance
- GET /api/player/{id}/cross-season     — all seasons overlay data
- GET /api/ratings                      — global Glicko-2 leaderboard
- GET /api/player/{id}/rating-history   — rating change graph
- POST /api/predict/{season_id}         — AI race prediction
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from backend.db.base import get_db
from backend.models.models import (
    Player, Race, RaceResult, RaceEvent, Season,
    ChampionshipStanding, PlayerRating, RatingHistory, PlayerAchievement, Achievement,
    WebUser,
)
from backend.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["analytics"])


# ---------------------------------------------------------------------------
# GET /api/player/{id}/trends
# ---------------------------------------------------------------------------

@router.get("/player/{player_id}/trends")
async def get_player_trends(player_id: int, season_id: int | None = None,
                            db: AsyncSession = Depends(get_db)):
    query = (
        select(RaceResult, Race.round_number, Race.track_name, Race.season_id)
        .join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player_id)
    )
    if season_id:
        query = query.where(RaceResult.season_id == season_id)
    query = query.order_by(Race.raced_at)

    res = await db.execute(query)
    rows = res.all()

    points_cumulative = 0
    positions = []
    data_points = []

    for rr, round_num, track_name, sid in rows:
        points_cumulative += rr.points
        if rr.position:
            positions.append(rr.position)
        avg_pos = sum(positions) / len(positions) if positions else None
        grid_delta = (rr.grid_position - rr.position) if rr.grid_position and rr.position else None

        data_points.append({
            "race_id":            rr.race_id,
            "season_id":          sid,
            "round":              round_num,
            "track":              track_name,
            "position":           rr.position,
            "grid_position":      rr.grid_position,
            "grid_delta":         grid_delta,
            "points":             rr.points,
            "points_cumulative":  round(points_cumulative, 1),
            "avg_position":       round(avg_pos, 2) if avg_pos else None,
            "has_fastest_lap":    rr.has_fastest_lap,
            "result_status":      rr.result_status,
        })

    return {"player_id": player_id, "trends": data_points}


# ---------------------------------------------------------------------------
# GET /api/player/{id}/h2h/{other_id}
# ---------------------------------------------------------------------------

@router.get("/player/{player_id}/h2h/{other_id}")
async def get_h2h(player_id: int, other_id: int, db: AsyncSession = Depends(get_db)):
    # Get all races where both participated
    p1_res = await db.execute(
        select(RaceResult).where(RaceResult.player_id == player_id)
    )
    p2_res = await db.execute(
        select(RaceResult).where(RaceResult.player_id == other_id)
    )
    p1_results = {r.race_id: r for r in p1_res.scalars().all()}
    p2_results = {r.race_id: r for r in p2_res.scalars().all()}

    common_races = set(p1_results.keys()) & set(p2_results.keys())
    if not common_races:
        return {"races_together": 0}

    # Load race info
    races_res = await db.execute(
        select(Race).where(Race.id.in_(common_races)).order_by(Race.raced_at)
    )
    races = {r.id: r for r in races_res.scalars().all()}

    # Load player names
    p1 = await db.get(Player, player_id)
    p2 = await db.get(Player, other_id)

    p1_wins = 0
    p2_wins = 0
    p1_positions = []
    p2_positions = []
    p1_quali_wins = 0
    p2_quali_wins = 0
    race_details = []

    for rid in sorted(common_races, key=lambda r: races[r].raced_at if r in races else 0):
        r1 = p1_results[rid]
        r2 = p2_results[rid]
        race = races.get(rid)

        if r1.position and r2.position:
            if r1.position < r2.position:
                p1_wins += 1
            else:
                p2_wins += 1
            p1_positions.append(r1.position)
            p2_positions.append(r2.position)

        if r1.grid_position and r2.grid_position:
            if r1.grid_position < r2.grid_position:
                p1_quali_wins += 1
            elif r2.grid_position < r1.grid_position:
                p2_quali_wins += 1

        race_details.append({
            "race_id":    rid,
            "round":      race.round_number if race else None,
            "track":      race.track_name if race else None,
            "p1_pos":     r1.position,
            "p2_pos":     r2.position,
            "p1_grid":    r1.grid_position,
            "p2_grid":    r2.grid_position,
            "p1_points":  r1.points,
            "p2_points":  r2.points,
        })

    return {
        "player_1":       {"id": player_id, "name": p1.name if p1 else ""},
        "player_2":       {"id": other_id,  "name": p2.name if p2 else ""},
        "races_together":  len(common_races),
        "race_wins":       {"p1": p1_wins, "p2": p2_wins},
        "quali_wins":      {"p1": p1_quali_wins, "p2": p2_quali_wins},
        "avg_position":    {
            "p1": round(sum(p1_positions) / len(p1_positions), 2) if p1_positions else None,
            "p2": round(sum(p2_positions) / len(p2_positions), 2) if p2_positions else None,
        },
        "total_points":    {
            "p1": sum(r1.points for r1 in p1_results.values() if r1.race_id in common_races),
            "p2": sum(r2.points for r2 in p2_results.values() if r2.race_id in common_races),
        },
        "races": race_details,
    }


# ---------------------------------------------------------------------------
# GET /api/player/{id}/tyre-stats
# ---------------------------------------------------------------------------

@router.get("/player/{player_id}/tyre-stats")
async def get_tyre_stats(player_id: int, season_id: int | None = None,
                         db: AsyncSession = Depends(get_db)):
    query = select(RaceResult).where(RaceResult.player_id == player_id)
    if season_id:
        query = query.where(RaceResult.season_id == season_id)

    res = await db.execute(query)
    results = res.scalars().all()

    compound_data: dict[str, dict] = {}  # compound → {laps: [], lap_times: []}

    for rr in results:
        stints = rr.tyre_stints or []
        for stint in stints:
            compound = stint.get("compound", "Unknown")
            if isinstance(compound, int):
                compound = _compound_name(compound)
            cd = compound_data.setdefault(compound, {"total_laps": 0, "stint_count": 0})
            end_lap = stint.get("end_lap", 0) or 0
            cd["total_laps"] += max(end_lap, 1)
            cd["stint_count"] += 1

    return {
        "player_id": player_id,
        "compounds": [
            {
                "compound":    c,
                "total_laps":  d["total_laps"],
                "stint_count": d["stint_count"],
                "avg_stint_length": round(d["total_laps"] / d["stint_count"], 1) if d["stint_count"] else 0,
            }
            for c, d in sorted(compound_data.items())
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/player/{id}/cross-season
# ---------------------------------------------------------------------------

@router.get("/player/{player_id}/cross-season")
async def get_cross_season(player_id: int, db: AsyncSession = Depends(get_db)):
    """Per-season breakdown with trends for overlay charts."""
    standings_res = await db.execute(
        select(ChampionshipStanding, Season.name, Season.status)
        .join(Season, ChampionshipStanding.season_id == Season.id)
        .where(ChampionshipStanding.player_id == player_id)
        .order_by(Season.id)
    )
    rows = standings_res.all()

    # Also get per-race data for overlay charts
    races_res = await db.execute(
        select(RaceResult, Race.round_number, Race.season_id)
        .join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player_id)
        .order_by(Race.season_id, Race.round_number)
    )
    race_rows = races_res.all()

    # Group races by season
    season_races: dict[int, list] = {}
    for rr, rnd, sid in race_rows:
        season_races.setdefault(sid, []).append({
            "round": rnd, "position": rr.position,
            "points": rr.points, "grid": rr.grid_position,
        })

    seasons = []
    for cs, sname, sstatus in rows:
        seasons.append({
            "season_id":        cs.season_id,
            "season_name":      sname,
            "status":           sstatus,
            "position":         cs.position,
            "points":           cs.total_points,
            "wins":             cs.wins,
            "podiums":          cs.podiums,
            "fastest_laps":     cs.fastest_laps,
            "dnfs":             cs.dnfs,
            "consistency_index": cs.consistency_index,
            "avg_grid_delta":   cs.avg_grid_delta,
            "races":            season_races.get(cs.season_id, []),
        })

    return {"player_id": player_id, "seasons": seasons}


# ---------------------------------------------------------------------------
# GET /api/ratings
# ---------------------------------------------------------------------------

@router.get("/ratings")
async def get_ratings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(PlayerRating, Player.name)
        .join(Player, Player.id == PlayerRating.player_id)
        .order_by(PlayerRating.rating.desc())
    )
    rows = res.all()
    return [
        {
            "player_id":   pr.player_id,
            "name":        pname,
            "rating":      round(pr.rating, 1),
            "rd":          round(pr.rd, 1),
            "peak_rating": round(pr.peak_rating, 1),
            "wins":        pr.wins,
            "losses":      pr.losses,
            "races_rated": pr.races_rated,
        }
        for pr, pname in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/player/{id}/rating-history
# ---------------------------------------------------------------------------

@router.get("/player/{player_id}/rating-history")
async def get_rating_history(player_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(RatingHistory, Race.round_number, Race.track_name, Race.season_id)
        .join(Race, Race.id == RatingHistory.race_id)
        .where(RatingHistory.player_id == player_id)
        .order_by(RatingHistory.recorded_at)
    )
    rows = res.all()
    return [
        {
            "race_id":       rh.race_id,
            "season_id":     sid,
            "round":         rnd,
            "track":         track,
            "rating_before": round(rh.rating_before, 1),
            "rating_after":  round(rh.rating_after, 1),
            "change":        round(rh.rating_after - rh.rating_before, 1),
        }
        for rh, rnd, track, sid in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/player/{id}/full-profile
# ---------------------------------------------------------------------------

@router.get("/player/{player_id}/full-profile")
async def get_full_profile(player_id: int, db: AsyncSession = Depends(get_db)):
    """
    Complete profile data for public profile page.
    Combines stats, rating, achievements, trends, season history.
    """
    player_res = await db.execute(select(Player).where(Player.id == player_id))
    player = player_res.scalars().first()
    if not player:
        raise HTTPException(404, "Player not found")

    # Basic stats
    results_res = await db.execute(select(RaceResult).where(RaceResult.player_id == player_id))
    results = results_res.scalars().all()

    positions = [r.position for r in results if r.position]
    grid_deltas = [r.grid_position - r.position for r in results if r.grid_position and r.position]

    stats = {
        "races":        len(results),
        "total_points": sum(r.points for r in results),
        "wins":         sum(1 for r in results if r.position == 1),
        "podiums":      sum(1 for r in results if r.position and r.position <= 3),
        "dnfs":         sum(1 for r in results if r.result_status in (4, 6)),
        "fastest_laps": sum(1 for r in results if r.has_fastest_lap),
        "avg_position": round(sum(positions) / len(positions), 2) if positions else None,
        "best_finish":  min(positions) if positions else None,
        "win_rate":     round(sum(1 for r in results if r.position == 1) / len(results) * 100, 1) if results else 0,
        "podium_rate":  round(sum(1 for r in results if r.position and r.position <= 3) / len(results) * 100, 1) if results else 0,
        "avg_grid_delta": round(sum(grid_deltas) / len(grid_deltas), 2) if grid_deltas else None,
        "best_recovery": max(grid_deltas) if grid_deltas else None,
        "worst_drop":    min(grid_deltas) if grid_deltas else None,
    }

    # Rating
    rating_res = await db.execute(
        select(PlayerRating).where(PlayerRating.player_id == player_id)
    )
    rating_obj = rating_res.scalars().first()
    rating = {
        "rating":      round(rating_obj.rating, 1) if rating_obj else 1500,
        "rd":          round(rating_obj.rd, 1) if rating_obj else 350,
        "peak_rating": round(rating_obj.peak_rating, 1) if rating_obj else 1500,
        "races_rated": rating_obj.races_rated if rating_obj else 0,
    }

    # Achievements
    ach_res = await db.execute(
        select(PlayerAchievement, Achievement)
        .join(Achievement, Achievement.id == PlayerAchievement.achievement_id)
        .where(PlayerAchievement.player_id == player_id)
        .order_by(PlayerAchievement.unlocked_at)
    )
    achievements = [
        {
            "code":        a.code,
            "name":        a.name,
            "description": a.description,
            "icon":        a.icon,
            "unlocked_at": pa.unlocked_at.isoformat() if pa.unlocked_at else None,
        }
        for pa, a in ach_res.all()
    ]

    # Season history
    sh_res = await db.execute(
        select(ChampionshipStanding, Season.name, Season.status)
        .join(Season, ChampionshipStanding.season_id == Season.id)
        .where(ChampionshipStanding.player_id == player_id)
        .order_by(Season.id)
    )
    season_history = [
        {
            "season_id":        cs.season_id,
            "season_name":      sname,
            "status":           sstatus,
            "position":         cs.position,
            "points":           cs.total_points,
            "wins":             cs.wins,
            "podiums":          cs.podiums,
            "fastest_laps":     cs.fastest_laps,
            "dnfs":             cs.dnfs,
            "consistency_index": cs.consistency_index,
            "avg_grid_delta":   cs.avg_grid_delta,
            "team_name":        cs.team_name,
        }
        for cs, sname, sstatus in sh_res.all()
    ]

    # Last team/driver assignment
    latest_result = next(
        iter(sorted(results, key=lambda r: r.race_id, reverse=True)),
        None,
    )

    return {
        "player_id":      player_id,
        "name":           player.name,
        "avatar_url":     player.avatar_url,
        "steam_url":      player.steam_url,
        "created_at":     player.created_at.isoformat() if player.created_at else None,
        "current_team":   latest_result.team_name if latest_result else None,
        "current_driver": latest_result.driver_name if latest_result else None,
        "stats":          stats,
        "rating":         rating,
        "achievements":   achievements,
        "season_history": season_history,
    }


# ---------------------------------------------------------------------------
# POST /api/predict/{season_id}
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    track_id: int | None = None


@router.post("/predict/{season_id}")
async def predict_race(
    season_id: int,
    req: PredictRequest = PredictRequest(),
    db: AsyncSession = Depends(get_db),
    _: WebUser = Depends(get_current_user),
):
    """AI prediction for next race using Groq."""
    import os, httpx

    # Get standings
    standings_res = await db.execute(
        select(ChampionshipStanding).where(
            ChampionshipStanding.season_id == season_id,
            ChampionshipStanding.is_human == True,  # noqa
        ).order_by(ChampionshipStanding.total_points.desc())
    )
    standings = standings_res.scalars().all()

    if not standings:
        raise HTTPException(400, "No standings data")

    # Get last 5 race results per human
    player_ids = [s.player_id for s in standings if s.player_id]
    recent_res = await db.execute(
        select(RaceResult, Race.round_number, Race.track_name)
        .join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id.in_(player_ids), RaceResult.season_id == season_id)
        .order_by(Race.round_number.desc()).limit(len(player_ids) * 5)
    )
    recent = recent_res.all()

    # Build context for AI
    standings_text = "\n".join(
        f"P{i+1}. {s.driver_name} ({s.team_name}) — {s.total_points} pts, "
        f"{s.wins}W {s.podiums}P {s.dnfs}DNF, CI={s.consistency_index or 'N/A'}"
        for i, s in enumerate(standings)
    )

    recent_text = "\n".join(
        f"R{rnd} {track}: {rr.driver_name} P{rr.position}"
        for rr, rnd, track in recent[:20]
    )

    prompt = f"""Ты аналитик F1 лиги. Спрогнозируй результаты следующей гонки.

Текущие standings:
{standings_text}

Последние результаты:
{recent_text}

Дай прогноз финишных позиций для каждого пилота с кратким обоснованием (2-3 предложения на каждого).
Формат: P1. Имя — причина"""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(500, "GROQ_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "Ты спортивный аналитик F1 лиги. Отвечай на русском."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, "AI prediction failed")

        data = resp.json()
        prediction = data["choices"][0]["message"]["content"]

    return {"season_id": season_id, "prediction": prediction}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compound_name(compound_id: int) -> str:
    names = {
        16: "Soft", 17: "Medium", 18: "Hard",
        7: "Inter", 8: "Wet",
        0: "C5", 1: "C4", 2: "C3", 3: "C2", 4: "C1",
    }
    return names.get(compound_id, f"C{compound_id}")
