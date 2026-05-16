"""
Contract generation and acceptance flow.
"""
from __future__ import annotations

import os
import statistics

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.base import get_database_url
from backend.models.models import User, Race, RaceResult, SeasonContract


def _groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def _groq_model() -> str:
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _groq_url() -> str:
    return os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")


TEAM_TIER: dict[int, int] = {
    2: 9,
    8: 8,
    1: 7,
    0: 6,
    4: 5,
    5: 4,
    6: 3,
    9: 2,
    3: 1,
    7: 0,
}


def _calc_rating(results: list[RaceResult]) -> float:
    if not results:
        return 0.0

    positions = [result.position for result in results if result.position]
    wins = sum(1 for result in results if result.position == 1)
    points_sum = sum(result.points for result in results)
    total = len(results)

    avg_pos = sum(positions) / len(positions) if positions else 20
    win_rate = wins / total
    consistency = 1 / (statistics.stdev(positions) + 1) if len(positions) > 1 else 0.5
    points_per_race = points_sum / total

    score = (
        (20 - avg_pos) / 19 * 0.40
        + win_rate * 0.25
        + min(consistency, 1.0) * 0.20
        + min(points_per_race / 25, 1.0) * 0.15
    )
    return round(score * 100, 1)


async def generate_contracts(season_id: int) -> list[dict]:
    engine = create_async_engine(get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    generated: list[dict] = []

    try:
        async with session_factory() as db:
            races_result = await db.execute(select(Race).where(Race.season_id == season_id))
            race_ids = [race.id for race in races_result.scalars().all()]

            race_results = await db.execute(
                select(RaceResult).where(
                    RaceResult.race_id.in_(race_ids),
                    RaceResult.is_human == True,  # noqa: E712
                )
            )
            all_results = race_results.scalars().all()

            by_player: dict[int, list[RaceResult]] = {}
            for result in all_results:
                if result.user_id is None:
                    continue
                by_player.setdefault(result.user_id, []).append(result)

            contracts_result = await db.execute(
                select(SeasonContract).where(SeasonContract.season_id == season_id)
            )
            current_contracts = {contract.user_id: contract for contract in contracts_result.scalars().all()}

            for player_id, results in by_player.items():
                player = await db.get(User, player_id)
                if not player:
                    continue

                rating = _calc_rating(results)
                current_contract = current_contracts.get(player_id)
                current_team = current_contract.team_id if current_contract else -1
                current_tier = TEAM_TIER.get(current_team, 5)
                offers = _pick_offers(rating, current_team, current_tier)

                for offer in offers:
                    offer["narrative"] = await _generate_narrative(
                        player.name,
                        rating,
                        results,
                        offer,
                        current_contract,
                    )

                generated.append(
                    {
                        "player_id": player_id,
                        "player_name": player.name,
                        "rating": rating,
                        "current_team": current_contract.team_name if current_contract else "Free Agent",
                        "offers": offers,
                    }
                )
    finally:
        await engine.dispose()

    return sorted(generated, key=lambda item: -item["rating"])


def _pick_offers(rating: float, current_team: int, current_tier: int) -> list[dict]:
    from shared.f1_mappings import TEAMS

    offers: list[dict] = []
    all_teams = list(TEAMS.items())

    hot_tier = min(9, current_tier + max(1, int(rating / 30)))
    hot_candidates = [
        (team_id, info)
        for team_id, info in all_teams
        if TEAM_TIER.get(team_id, 5) >= hot_tier and team_id != current_team
    ]
    if hot_candidates:
        best = max(hot_candidates, key=lambda item: TEAM_TIER.get(item[0], 0))
        offers.append(
            {
                "tier": "HOT OFFER",
                "team_id": best[0],
                "team_name": best[1]["name"],
                "team_color": best[1]["color"],
            }
        )

    mid_candidates = [
        (team_id, info)
        for team_id, info in all_teams
        if TEAM_TIER.get(team_id, 5) == max(0, current_tier - 1) and team_id != current_team
    ]
    if not mid_candidates:
        mid_candidates = [(team_id, info) for team_id, info in all_teams if team_id != current_team][:2]
    if mid_candidates:
        mid = mid_candidates[len(mid_candidates) // 2]
        offers.append(
            {
                "tier": "OFFER",
                "team_id": mid[0],
                "team_name": mid[1]["name"],
                "team_color": mid[1]["color"],
            }
        )

    long_candidates = [
        (team_id, info)
        for team_id, info in all_teams
        if TEAM_TIER.get(team_id, 5) <= max(0, current_tier - 2) and team_id != current_team
    ]
    if long_candidates:
        worst = min(long_candidates, key=lambda item: TEAM_TIER.get(item[0], 0))
        offers.append(
            {
                "tier": "LONG-SHOT",
                "team_id": worst[0],
                "team_name": worst[1]["name"],
                "team_color": worst[1]["color"],
            }
        )

    return offers[:3]


async def _generate_narrative(
    player_name: str,
    rating: float,
    results: list[RaceResult],
    offer: dict,
    current_contract: SeasonContract | None,
) -> str:
    if not _groq_api_key():
        return _fallback_narrative(offer["tier"], rating)

    positions = [result.position for result in results if result.position]
    wins = sum(1 for result in results if result.position == 1)
    avg_pos = sum(positions) / len(positions) if positions else 0
    current_team = current_contract.team_name if current_contract else "Free Agent"
    prompt = (
        f"Команда {offer['team_name']} предлагает контракт пилоту {player_name}.\n"
        f"Статистика пилота: {len(results)} гонок, {wins} побед, средняя позиция {avg_pos:.1f}, "
        f"рейтинг {rating:.0f}/100. Текущая команда: {current_team}.\n"
        f"Тип предложения: {offer['tier']}.\n\n"
        "Напиши 2 предложения от имени команды: почему они хотят этого пилота. "
        "Конкретно, без клише. Русский язык."
    )

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                _groq_url(),
                json={
                    "model": _groq_model(),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 120,
                    "temperature": 0.8,
                },
                headers={"Authorization": f"Bearer {_groq_api_key()}"},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return _fallback_narrative(offer["tier"], rating)


def _fallback_narrative(tier: str, rating: float) -> str:
    if tier == "HOT OFFER":
        return "Ваши результаты впечатлили нас. Мы готовы предложить место в сильной команде."
    if tier == "OFFER":
        return "Мы следили за вашими выступлениями. В составе есть свободное место под ваш профиль."
    return "Мы видим потенциал и готовы дать шанс проявить себя."


async def apply_contract(player_id: int, new_team_id: int, new_season_id: int) -> dict:
    engine = create_async_engine(get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    from shared.f1_mappings import DRIVERS, get_team

    try:
        async with session_factory() as db:
            existing_result = await db.execute(
                select(SeasonContract).where(
                    SeasonContract.season_id == new_season_id,
                    SeasonContract.team_id == new_team_id,
                )
            )
            taken_driver_ids = {contract.driver_id for contract in existing_result.scalars().all()}

            team_info = get_team(new_team_id)
            team_drivers = [
                (driver_id, driver)
                for driver_id, driver in DRIVERS.items()
                if driver.get("team_id") == new_team_id and driver_id not in taken_driver_ids
            ]
            if not team_drivers:
                return {"ok": False, "error": "No available drivers in this team"}

            driver_id, driver_info = team_drivers[0]

            old_result = await db.execute(
                select(SeasonContract).where(
                    SeasonContract.season_id == new_season_id,
                    SeasonContract.user_id == player_id,
                )
            )
            old_contract = old_result.scalars().first()
            if old_contract:
                await db.delete(old_contract)

            db.add(
                SeasonContract(
                    season_id=new_season_id,
                    user_id=player_id,
                    driver_id=driver_id,
                    driver_name=driver_info["name"],
                    team_id=new_team_id,
                    team_name=team_info["name"],
                )
            )
            await db.commit()
    finally:
        await engine.dispose()

    return {
        "ok": True,
        "team_name": team_info["name"],
        "driver_name": driver_info["name"],
        "team_color": team_info["color"],
    }
