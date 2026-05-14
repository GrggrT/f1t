"""
Пересчитывает WDC + WCC standings после каждой гонки.
Включает consistency_index и avg_grid_delta.
Запускается как BackgroundTask из /api/race/submit.
"""
import statistics
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, delete
from backend.db.base import get_database_url
from backend.models.models import Race, RaceResult, ChampionshipStanding, ConstructorStanding
from shared.points_system import calc_wdc, calc_wcc
from shared.f1_mappings import get_team


def _calc_consistency(positions: list[int]) -> float | None:
    """Consistency Index: 1 - (stdev / max_possible_stdev). Range 0.0–1.0."""
    if len(positions) < 2:
        return None
    sd = statistics.stdev(positions)
    # Max possible stdev for positions 1-20 ≈ 9.5
    max_sd = 9.5
    return round(max(0.0, 1.0 - sd / max_sd), 3)


def _calc_avg_grid_delta(results: list) -> float | None:
    """Average positions gained from grid. Positive = gained, negative = lost."""
    deltas = []
    for r in results:
        if r.grid_position and r.position:
            deltas.append(r.grid_position - r.position)
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 2)


async def recalc_standings(season_id: int) -> None:
    engine = create_async_engine(get_database_url(), echo=False, pool_size=5, max_overflow=0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            # Загружаем все результаты сезона
            races_res = await db.execute(select(Race).where(Race.season_id == season_id))
            race_ids = [r.id for r in races_res.scalars().all()]

            if not race_ids:
                return

            results_res = await db.execute(
                select(RaceResult).where(RaceResult.race_id.in_(race_ids))
            )
            results = results_res.scalars().all()

            # Группируем по driver_id для consistency/grid-delta расчётов
            by_driver: dict[int, list[RaceResult]] = {}
            for r in results:
                by_driver.setdefault(r.driver_id, []).append(r)

            # Формируем данные для calc_wdc
            raw = [
                {
                    "driver_id":       r.driver_id,
                    "driver_name":     r.driver_name,
                    "team_id":         r.team_id,
                    "team_name":       r.team_name,
                    "player_id":       r.player_id,
                    "is_human":        r.is_human,
                    "position":        r.position or 99,
                    "has_fastest_lap": r.has_fastest_lap,
                    "result_status":   r.result_status,
                }
                for r in results
            ]

            wdc = calc_wdc(raw)
            wcc = calc_wcc(wdc)

            # Удаляем старые standings и вставляем новые
            await db.execute(
                delete(ChampionshipStanding).where(ChampionshipStanding.season_id == season_id)
            )
            await db.execute(
                delete(ConstructorStanding).where(ConstructorStanding.season_id == season_id)
            )

            for i, entry in enumerate(wdc):
                did = entry["driver_id"]
                driver_results = by_driver.get(did, [])
                positions = [r.position for r in driver_results if r.position]

                db.add(ChampionshipStanding(
                    season_id=season_id,
                    driver_id=entry["driver_id"],
                    driver_name=entry["driver_name"],
                    player_id=entry["player_id"],
                    is_human=entry["is_human"],
                    team_id=entry["team_id"],
                    team_name=entry["team_name"],
                    total_points=entry["total_points"],
                    wins=entry["wins"],
                    podiums=entry["podiums"],
                    fastest_laps=entry["fastest_laps"],
                    dnfs=entry["dnfs"],
                    best_finish=entry["best_finish"],
                    position=i + 1,
                    consistency_index=_calc_consistency(positions),
                    avg_grid_delta=_calc_avg_grid_delta(driver_results),
                ))

            for entry in wcc:
                drivers = entry.get("drivers", [])
                db.add(ConstructorStanding(
                    season_id=season_id,
                    team_id=entry["team_id"],
                    team_name=entry["team_name"],
                    total_points=entry["total_points"],
                    wins=entry["wins"],
                    driver_1_name=drivers[0] if len(drivers) > 0 else None,
                    driver_2_name=drivers[1] if len(drivers) > 1 else None,
                ))

            await db.commit()
    finally:
        await engine.dispose()
