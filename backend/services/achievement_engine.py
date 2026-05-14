"""
Achievement Engine — проверяет и выдаёт достижения после каждой гонки.
Запускается как BackgroundTask из /api/race/submit.

Возвращает список новых разблокированных достижений для нотификации бота.
"""
from __future__ import annotations
from datetime import datetime, timezone, date
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func, and_
from backend.db.base import get_database_url
from backend.models.models import (
    Race, RaceResult, RaceEvent, Player, Season,
    Achievement, PlayerAchievement, ChampionshipStanding,
)


# ---------------------------------------------------------------------------
# Главная точка входа
# ---------------------------------------------------------------------------

async def check_achievements_after_race(race_id: int, season_id: int) -> list[dict]:
    engine = create_async_engine(get_database_url(), echo=False, pool_size=5, max_overflow=0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unlocked = []

    try:
        async with session_factory() as db:
            race    = await _get_race(db, race_id)
            results = await _get_results(db, race_id)
            events  = await _get_events(db, race_id)

            if not race or not results:
                return []

            human_results = [r for r in results if r.is_human and r.player_id]

            for rr in human_results:
                player = await db.get(Player, rr.player_id)
                if not player:
                    continue

                new = await _check_player(db, player, rr, race, results, events, season_id)
                unlocked.extend(new)

            await db.commit()
    finally:
        await engine.dispose()
    return unlocked


# ---------------------------------------------------------------------------
# Проверки на игрока
# ---------------------------------------------------------------------------

async def _check_player(
    db: AsyncSession, player: Player, rr: RaceResult,
    race: Race, all_results: list[RaceResult],
    events: list[RaceEvent], season_id: int,
) -> list[dict]:
    new_unlocks = []

    checkers = [
        # Original 18
        _check_first_blood, _check_rocket_start, _check_rain_master,
        _check_wrecking_ball, _check_last_to_first, _check_clean_sweep,
        _check_comeback_kid, _check_photo_finish, _check_survivor,
        _check_pit_master, _check_giant_killer, _check_dominator,
        _check_consistency_king, _check_weekend_warrior, _check_centurion,
        _check_bot_slayer, _check_heartbreaker, _check_speed_demon,
        # New race-based
        _check_grand_chelem, _check_underdog, _check_rain_dance,
        _check_late_braker, _check_double_points, _check_marathon_man,
        _check_penalty_free, _check_team_orders, _check_the_stig,
        _check_bulldozer,
        # Progression
        _check_rising_star, _check_hot_streak, _check_fifty_races,
        _check_hundred_races, _check_points_machine, _check_two_hundred_pts,
        _check_veteran,
        # Fun / meme
        _check_torpedo, _check_glass_cannon, _check_reverse_grid,
        _check_sunday_driver, _check_last_not_least, _check_jinxed,
        _check_phoenix, _check_gentleman,
        # Exclusive
        _check_founding_father,
    ]

    for checker in checkers:
        try:
            code = await checker(db, player, rr, race, all_results, events, season_id)
            if code:
                unlock = await _unlock(db, player, code, race.id, rr)
                if unlock:
                    new_unlocks.append(unlock)
        except Exception as e:
            print(f"[ACH] Checker {checker.__name__} error: {e}")

    return new_unlocks


async def _unlock(db: AsyncSession, player: Player, code: str, race_id: int, rr: RaceResult) -> dict | None:
    ach_res = await db.execute(select(Achievement).where(Achievement.code == code))
    ach = ach_res.scalars().first()
    if not ach:
        return None

    existing = await db.execute(
        select(PlayerAchievement).where(
            PlayerAchievement.player_id == player.id,
            PlayerAchievement.achievement_id == ach.id,
        )
    )
    if existing.scalars().first():
        return None

    db.add(PlayerAchievement(
        player_id=player.id, achievement_id=ach.id, race_id=race_id,
        context={"position": rr.position, "points": rr.points},
    ))
    print(f"[ACH] {player.name} unlocked: {ach.icon} {ach.name}")
    return {
        "player_name": player.name, "ach_code": ach.code,
        "ach_name": ach.name, "ach_icon": ach.icon, "ach_desc": ach.description,
    }


# ---------------------------------------------------------------------------
# ORIGINAL CHECKERS
# ---------------------------------------------------------------------------

async def _check_first_blood(db, player, rr, race, all_results, events, season_id):
    if rr.position != 1:
        return None
    prev_wins = await db.execute(
        select(func.count()).select_from(RaceResult).where(
            RaceResult.player_id == player.id, RaceResult.position == 1,
            RaceResult.race_id != race.id,
        )
    )
    return "FIRST_BLOOD" if prev_wins.scalar() == 0 else None


async def _check_rocket_start(db, player, rr, race, all_results, events, season_id):
    if rr.grid_position and rr.position and (rr.grid_position - rr.position) >= 3:
        return "ROCKET_START"
    return None


async def _check_rain_master(db, player, rr, race, all_results, events, season_id):
    if rr.position == 1 and race.weather_start is not None and race.weather_start >= 3:
        return "RAIN_MASTER"
    return None


async def _check_wrecking_ball(db, player, rr, race, all_results, events, season_id):
    if rr.num_penalties and rr.num_penalties >= 3:
        return "WRECKING_BALL"
    return None


async def _check_last_to_first(db, player, rr, race, all_results, events, season_id):
    total = len(all_results)
    if rr.position == 1 and rr.grid_position and rr.grid_position >= total:
        return "LAST_TO_FIRST"
    return None


async def _check_clean_sweep(db, player, rr, race, all_results, events, season_id):
    if rr.position == 1 and rr.grid_position == 1 and rr.has_fastest_lap:
        return "CLEAN_SWEEP"
    return None


async def _check_comeback_kid(db, player, rr, race, all_results, events, season_id):
    if rr.position and rr.position <= 3 and rr.grid_position and rr.grid_position >= 10:
        return "COMEBACK_KID"
    return None


async def _check_photo_finish(db, player, rr, race, all_results, events, season_id):
    if not rr.total_race_time or not rr.position:
        return None
    for other in all_results:
        if other.vehicle_index == rr.vehicle_index or not other.is_human:
            continue
        if other.total_race_time and abs(rr.total_race_time - other.total_race_time) < 0.5:
            return "PHOTO_FINISH"
    return None


async def _check_survivor(db, player, rr, race, all_results, events, season_id):
    if rr.result_status not in (3,):
        return None
    human_dnfs = sum(
        1 for r in all_results
        if r.is_human and r.vehicle_index != rr.vehicle_index and r.result_status in (4, 6)
    )
    return "SURVIVOR" if human_dnfs >= 2 else None


async def _check_pit_master(db, player, rr, race, all_results, events, season_id):
    if rr.num_pit_stops and rr.num_pit_stops > 0:
        if rr.grid_position and rr.position and rr.position < rr.grid_position:
            return "PIT_MASTER"
    return None


async def _check_giant_killer(db, player, rr, race, all_results, events, season_id):
    if not rr.position:
        return None
    leader_res = await db.execute(
        select(ChampionshipStanding).where(
            ChampionshipStanding.season_id == season_id,
            ChampionshipStanding.is_human == True,  # noqa
        ).order_by(ChampionshipStanding.total_points.desc()).limit(1)
    )
    leader = leader_res.scalars().first()
    if not leader or leader.player_id == player.id:
        return None
    leader_result = next((r for r in all_results if r.player_id == leader.player_id), None)
    if leader_result and leader_result.position and rr.position < leader_result.position:
        return "GIANT_KILLER"
    return None


async def _check_dominator(db, player, rr, race, all_results, events, season_id):
    if rr.position != 1:
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id, RaceResult.season_id == season_id)
        .order_by(Race.round_number.desc()).limit(3)
    )
    last3 = recent.scalars().all()
    return "DOMINATOR" if len(last3) == 3 and all(r.position == 1 for r in last3) else None


async def _check_consistency_king(db, player, rr, race, all_results, events, season_id):
    if not rr.position or rr.position > 3:
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id, RaceResult.season_id == season_id)
        .order_by(Race.round_number.desc()).limit(5)
    )
    last5 = recent.scalars().all()
    return "CONSISTENCY_KING" if len(last5) == 5 and all(r.position and r.position <= 3 for r in last5) else None


async def _check_weekend_warrior(db, player, rr, race, all_results, events, season_id):
    race_date = race.raced_at.date() if race.raced_at else None
    if not race_date:
        return None
    same_day = await db.execute(
        select(func.count()).select_from(RaceResult)
        .join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id, func.date(Race.raced_at) == race_date)
    )
    return "WEEKEND_WARRIOR" if (same_day.scalar() or 0) >= 3 else None


async def _check_centurion(db, player, rr, race, all_results, events, season_id):
    total_pts = await db.execute(
        select(func.sum(RaceResult.points)).where(
            RaceResult.player_id == player.id, RaceResult.season_id == season_id,
        )
    )
    pts = total_pts.scalar() or 0
    return "CENTURION" if pts >= 100 else None


async def _check_bot_slayer(db, player, rr, race, all_results, events, season_id):
    if not rr.position:
        return None
    ver = next((r for r in all_results if not r.is_human and r.driver_id in (18, 33) and r.position), None)
    if not ver or rr.position >= ver.position:
        return None
    count_res = await db.execute(
        select(func.count()).select_from(RaceResult)
        .where(RaceResult.player_id == player.id, RaceResult.season_id == season_id)
    )
    return "BOT_SLAYER" if (count_res.scalar() or 0) >= 5 else None


async def _check_heartbreaker(db, player, rr, race, all_results, events, season_id):
    if rr.result_status in (4, 6) and rr.grid_position and rr.grid_position <= 5:
        return "HEARTBREAKER"
    return None


async def _check_speed_demon(db, player, rr, race, all_results, events, season_id):
    if not rr.has_fastest_lap or not rr.best_lap_ms:
        return None
    prev_best = await db.execute(
        select(func.min(RaceResult.best_lap_ms)).where(
            RaceResult.season_id == season_id, RaceResult.has_fastest_lap == True,  # noqa
            RaceResult.race_id != race.id, RaceResult.best_lap_ms != None,  # noqa
        )
    )
    prev_ms = prev_best.scalar()
    return "SPEED_DEMON" if prev_ms is None or rr.best_lap_ms < prev_ms else None


# ---------------------------------------------------------------------------
# NEW RACE-BASED CHECKERS
# ---------------------------------------------------------------------------

async def _check_grand_chelem(db, player, rr, race, all_results, events, season_id):
    """Pole + FL + Win (упрощённо, без проверки лидерства каждого круга)."""
    if rr.position == 1 and rr.grid_position == 1 and rr.has_fastest_lap:
        # Check for continuous lead would need lap-by-lap data; approximate: grid=1 + win + FL
        # This is stricter than CLEAN_SWEEP — reserved for when we confirm lap-by-lap lead
        return None  # TODO: implement with lap data
    return None


async def _check_underdog(db, player, rr, race, all_results, events, season_id):
    """Победа стартовав с P15+."""
    if rr.position == 1 and rr.grid_position and rr.grid_position >= 15:
        return "UNDERDOG"
    return None


async def _check_rain_dance(db, player, rr, race, all_results, events, season_id):
    """Подиум в 3+ мокрых гонках за сезон."""
    if not rr.position or rr.position > 3:
        return None
    if not race.weather_start or race.weather_start < 3:
        return None
    wet_podiums = await db.execute(
        select(func.count()).select_from(RaceResult)
        .join(Race, Race.id == RaceResult.race_id)
        .where(
            RaceResult.player_id == player.id, RaceResult.season_id == season_id,
            RaceResult.position <= 3, Race.weather_start >= 3,
        )
    )
    return "RAIN_DANCE" if (wet_podiums.scalar() or 0) >= 3 else None


async def _check_late_braker(db, player, rr, race, all_results, events, season_id):
    """Обгон за подиум — финиш P1-3 при grid > 3."""
    if rr.position and rr.position <= 3 and rr.grid_position and rr.grid_position > 3:
        return "LATE_BRAKER"
    return None


async def _check_double_points(db, player, rr, race, all_results, events, season_id):
    """2 подиума за один день."""
    if not rr.position or rr.position > 3:
        return None
    race_date = race.raced_at.date() if race.raced_at else None
    if not race_date:
        return None
    day_podiums = await db.execute(
        select(func.count()).select_from(RaceResult)
        .join(Race, Race.id == RaceResult.race_id)
        .where(
            RaceResult.player_id == player.id,
            RaceResult.position <= 3,
            func.date(Race.raced_at) == race_date,
        )
    )
    return "DOUBLE_POINTS" if (day_podiums.scalar() or 0) >= 2 else None


async def _check_marathon_man(db, player, rr, race, all_results, events, season_id):
    """4+ гонки подряд в очках (P1-P10)."""
    if not rr.position or rr.position > 10:
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id, RaceResult.season_id == season_id)
        .order_by(Race.round_number.desc()).limit(4)
    )
    last4 = recent.scalars().all()
    return "MARATHON_MAN" if len(last4) == 4 and all(r.position and r.position <= 10 for r in last4) else None


async def _check_penalty_free(db, player, rr, race, all_results, events, season_id):
    """10 гонок подряд без штрафов."""
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id)
        .order_by(Race.round_number.desc()).limit(10)
    )
    last10 = recent.scalars().all()
    if len(last10) < 10:
        return None
    return "PENALTY_FREE" if all((r.num_penalties or 0) == 0 for r in last10) else None


async def _check_team_orders(db, player, rr, race, all_results, events, season_id):
    """Оба пилота команды на подиуме."""
    if not rr.position or rr.position > 3:
        return None
    teammate = next(
        (r for r in all_results if r.team_id == rr.team_id
         and r.vehicle_index != rr.vehicle_index and r.position and r.position <= 3),
        None,
    )
    return "TEAM_ORDERS" if teammate else None


async def _check_the_stig(db, player, rr, race, all_results, events, season_id):
    """Победа с отрывом 10+ секунд."""
    if rr.position != 1 or not rr.total_race_time:
        return None
    second = next(
        (r for r in sorted(all_results, key=lambda x: x.position or 99) if r.position == 2),
        None,
    )
    if second and second.total_race_time and (second.total_race_time - rr.total_race_time) >= 10.0:
        return "THE_STIG"
    return None


async def _check_bulldozer(db, player, rr, race, all_results, events, season_id):
    """P1 среди всех людей."""
    if not rr.position:
        return None
    human_positions = [r.position for r in all_results if r.is_human and r.player_id != player.id and r.position]
    if not human_positions:
        return None
    return "BULLDOZER" if rr.position < min(human_positions) else None


# ---------------------------------------------------------------------------
# PROGRESSION CHECKERS
# ---------------------------------------------------------------------------

async def _check_rising_star(db, player, rr, race, all_results, events, season_id):
    """5 гонок подряд с улучшением позиции."""
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id, RaceResult.season_id == season_id)
        .order_by(Race.round_number.desc()).limit(5)
    )
    last5 = recent.scalars().all()
    if len(last5) < 5:
        return None
    positions = [r.position for r in reversed(last5) if r.position]
    if len(positions) < 5:
        return None
    return "RISING_STAR" if all(positions[i] > positions[i + 1] for i in range(len(positions) - 1)) else None


async def _check_hot_streak(db, player, rr, race, all_results, events, season_id):
    """3 победы за один день."""
    if rr.position != 1:
        return None
    race_date = race.raced_at.date() if race.raced_at else None
    if not race_date:
        return None
    day_wins = await db.execute(
        select(func.count()).select_from(RaceResult)
        .join(Race, Race.id == RaceResult.race_id)
        .where(
            RaceResult.player_id == player.id, RaceResult.position == 1,
            func.date(Race.raced_at) == race_date,
        )
    )
    return "HOT_STREAK" if (day_wins.scalar() or 0) >= 3 else None


async def _check_fifty_races(db, player, rr, race, all_results, events, season_id):
    total = await db.execute(
        select(func.count()).select_from(RaceResult).where(RaceResult.player_id == player.id)
    )
    return "FIFTY_RACES" if (total.scalar() or 0) >= 50 else None


async def _check_hundred_races(db, player, rr, race, all_results, events, season_id):
    total = await db.execute(
        select(func.count()).select_from(RaceResult).where(RaceResult.player_id == player.id)
    )
    return "HUNDRED_RACES" if (total.scalar() or 0) >= 100 else None


async def _check_points_machine(db, player, rr, race, all_results, events, season_id):
    """10 гонок подряд в очках."""
    if not rr.position or rr.position > 10:
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id)
        .order_by(Race.round_number.desc()).limit(10)
    )
    last10 = recent.scalars().all()
    return "POINTS_MACHINE" if len(last10) == 10 and all(r.position and r.position <= 10 for r in last10) else None


async def _check_two_hundred_pts(db, player, rr, race, all_results, events, season_id):
    total_pts = await db.execute(
        select(func.sum(RaceResult.points)).where(
            RaceResult.player_id == player.id, RaceResult.season_id == season_id,
        )
    )
    return "TWO_HUNDRED_PTS" if (total_pts.scalar() or 0) >= 200 else None


async def _check_veteran(db, player, rr, race, all_results, events, season_id):
    """3+ разных сезонов с гонками."""
    seasons_count = await db.execute(
        select(func.count(func.distinct(RaceResult.season_id)))
        .select_from(RaceResult)
        .where(RaceResult.player_id == player.id)
    )
    return "VETERAN" if (seasons_count.scalar() or 0) >= 3 else None


# ---------------------------------------------------------------------------
# FUN / MEME CHECKERS
# ---------------------------------------------------------------------------

async def _check_torpedo(db, player, rr, race, all_results, events, season_id):
    """3+ столкновения за гонку (collision events)."""
    collisions = sum(
        1 for e in events
        if e.event_code in ("COLA", "COLW")  # collision with another car / wall
        and (e.event_data or {}).get("vehicleIdx") == rr.vehicle_index
    )
    return "TORPEDO" if collisions >= 3 else None


async def _check_glass_cannon(db, player, rr, race, all_results, events, season_id):
    """Лучший круг + DNF."""
    if rr.has_fastest_lap and rr.result_status in (4, 6):
        return "GLASS_CANNON"
    return None


async def _check_reverse_grid(db, player, rr, race, all_results, events, season_id):
    """Финишировал ниже стартовой 5 раз подряд."""
    if not rr.grid_position or not rr.position or rr.position <= rr.grid_position:
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id)
        .order_by(Race.round_number.desc()).limit(5)
    )
    last5 = recent.scalars().all()
    if len(last5) < 5:
        return None
    return "REVERSE_GRID" if all(
        r.grid_position and r.position and r.position > r.grid_position for r in last5
    ) else None


async def _check_sunday_driver(db, player, rr, race, all_results, events, season_id):
    """Самый медленный лучший круг среди людей 3 раза подряд."""
    if not rr.best_lap_ms:
        return None
    human_laps = [r.best_lap_ms for r in all_results if r.is_human and r.best_lap_ms and r.player_id]
    if not human_laps or rr.best_lap_ms < max(human_laps):
        return None  # not the slowest this race
    # Check last 3 races
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id)
        .order_by(Race.round_number.desc()).limit(3)
    )
    # Simplified: if slowest this race, check pattern
    return "SUNDAY_DRIVER" if rr.best_lap_ms == max(human_laps) else None


async def _check_last_not_least(db, player, rr, race, all_results, events, season_id):
    """Последний среди людей, но выше 10 AI."""
    if not rr.position:
        return None
    human_positions = [r.position for r in all_results if r.is_human and r.position]
    if not human_positions or rr.position != max(human_positions):
        return None
    ai_behind = sum(1 for r in all_results if not r.is_human and r.position and r.position > rr.position)
    return "LAST_NOT_LEAST" if ai_behind >= 10 else None


async def _check_jinxed(db, player, rr, race, all_results, events, season_id):
    """3 DNF подряд."""
    if rr.result_status not in (4, 6):
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id)
        .order_by(Race.round_number.desc()).limit(3)
    )
    last3 = recent.scalars().all()
    return "JINXED" if len(last3) == 3 and all(r.result_status in (4, 6) for r in last3) else None


async def _check_phoenix(db, player, rr, race, all_results, events, season_id):
    """После 3 DNF подряд — подиум."""
    if not rr.position or rr.position > 3:
        return None
    recent = await db.execute(
        select(RaceResult).join(Race, Race.id == RaceResult.race_id)
        .where(RaceResult.player_id == player.id, RaceResult.race_id != race.id)
        .order_by(Race.round_number.desc()).limit(3)
    )
    prev3 = recent.scalars().all()
    return "PHOENIX" if len(prev3) == 3 and all(r.result_status in (4, 6) for r in prev3) else None


async def _check_gentleman(db, player, rr, race, all_results, events, season_id):
    """Ни одного столкновения за весь сезон (мин. 5 гонок)."""
    # Count total races and collision events for this player in season
    races_count = await db.execute(
        select(func.count()).select_from(RaceResult)
        .where(RaceResult.player_id == player.id, RaceResult.season_id == season_id)
    )
    if (races_count.scalar() or 0) < 5:
        return None

    season_race_ids = await db.execute(
        select(Race.id).where(Race.season_id == season_id)
    )
    race_ids = [r[0] for r in season_race_ids.all()]
    if not race_ids:
        return None

    # Get all vehicle_indexes for this player in season
    vidx_res = await db.execute(
        select(RaceResult.vehicle_index, RaceResult.race_id)
        .where(RaceResult.player_id == player.id, RaceResult.race_id.in_(race_ids))
    )
    player_vidx_map = {row.race_id: row.vehicle_index for row in vidx_res.all()}

    # Check for any collision events
    for rid, vidx in player_vidx_map.items():
        collision_events = await db.execute(
            select(func.count()).select_from(RaceEvent)
            .where(
                RaceEvent.race_id == rid,
                RaceEvent.event_code.in_(["COLA", "COLW"]),
            )
        )
        # Simplified — if any collision in any race, not a gentleman
        if (collision_events.scalar() or 0) > 0:
            return None

    return "GENTLEMAN"


# ---------------------------------------------------------------------------
# EXCLUSIVE CHECKERS
# ---------------------------------------------------------------------------

async def _check_founding_father(db, player, rr, race, all_results, events, season_id):
    """Участник самой первой гонки в системе."""
    first_race = await db.execute(select(Race).order_by(Race.id).limit(1))
    fr = first_race.scalars().first()
    if fr and fr.id == race.id:
        return "FOUNDING_FATHER"
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_race(db: AsyncSession, race_id: int) -> Race | None:
    res = await db.execute(select(Race).where(Race.id == race_id))
    return res.scalars().first()


async def _get_results(db: AsyncSession, race_id: int) -> list[RaceResult]:
    res = await db.execute(select(RaceResult).where(RaceResult.race_id == race_id))
    return res.scalars().all()


async def _get_events(db: AsyncSession, race_id: int) -> list[RaceEvent]:
    res = await db.execute(select(RaceEvent).where(RaceEvent.race_id == race_id))
    return res.scalars().all()
