"""
AI race engineer debriefs after each race.
"""
from __future__ import annotations

import asyncio
import os

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.base import get_database_url
from backend.models.models import User, Race, RaceResult


def _groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def _groq_model() -> str:
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _groq_url() -> str:
    return os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")


def _stagger_sec() -> float:
    try:
        return float(os.getenv("AI_ENGINEER_STAGGER_SEC", "30"))
    except (TypeError, ValueError):
        return 30.0


class AICoachPayload:
    def __init__(self) -> None:
        self.player_name: str = ""
        self.driver_name: str = ""
        self.team_name: str = ""
        self.track_name: str = ""
        self.position: int = 0
        self.grid_position: int = 0
        self.total_players: int = 0
        self.points_earned: float = 0
        self.result_status: str = "Finished"
        self.best_lap_ms: int | None = None
        self.has_fastest_lap: bool = False
        self.penalties_sec: int = 0
        self.num_penalties: int = 0
        self.num_pit_stops: int = 0
        self.tyre_stints: list = []
        self.season_races: int = 0
        self.season_wins: int = 0
        self.season_podiums: int = 0
        self.season_points: float = 0
        self.season_avg_pos: float = 0
        self.season_dnfs: int = 0
        self.beaten_players: list[str] = []
        self.lost_to_players: list[str] = []
        self.positions_gained: int = 0
        self.weather: str = "Clear"


def _ms_to_laptime(ms: int | None) -> str:
    if not ms:
        return "-"
    total_seconds = ms / 1000
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}" if minutes else f"{seconds:.3f}s"


def _build_prompt(payload: AICoachPayload) -> str:
    pos_change = payload.grid_position - payload.position
    if pos_change > 0:
        pos_str = f"поднялся на {pos_change} позиции"
    elif pos_change < 0:
        pos_str = f"потерял {abs(pos_change)} позиции"
    else:
        pos_str = "стартовал и финишировал на одном месте"

    beaten = ", ".join(payload.beaten_players) if payload.beaten_players else "никого из игроков"
    lost_to = ", ".join(payload.lost_to_players) if payload.lost_to_players else "никому из игроков"
    stints = (
        " -> ".join(f"{item.get('compound', '?')} ({item.get('laps', '?')} кр)" for item in payload.tyre_stints)
        if payload.tyre_stints
        else "нет данных"
    )
    fastest_lap = "да" if payload.has_fastest_lap else "нет"

    return f"""Гонщик: {payload.player_name} (пилот: {payload.driver_name}, команда: {payload.team_name})
Гонка: {payload.track_name}
Результат: P{payload.position} из {payload.total_players} (стартовал с P{payload.grid_position}) — {pos_str}
Статус: {payload.result_status}
Очки за гонку: {payload.points_earned}
Лучший круг: {_ms_to_laptime(payload.best_lap_ms)} | Быстрейший круг: {fastest_lap}
Штрафы: {payload.num_penalties} шт, {payload.penalties_sec}с | Пит-стопы: {payload.num_pit_stops}
Шины: {stints}
Погода: {payload.weather}

Обогнал игроков: {beaten}
Проиграл игрокам: {lost_to}

Сезонная статистика ({payload.season_races} гонок):
Очки: {int(payload.season_points)} | Победы: {payload.season_wins} | Подиумы: {payload.season_podiums}
Средняя позиция: {payload.season_avg_pos:.1f} | DNF: {payload.season_dnfs}"""


SYSTEM_PROMPT = """Ты — инженер Формулы-1 уровня Питера Боннингтона.
Стиль: профессиональный, конкретный, с числами, без воды.
Структура ответа строго такая:
1. Одно предложение с общей оценкой гонки.
2. Два пункта со слабыми местами: проблема + рекомендация.
3. Один позитивный пункт.
4. Один фокус на следующую гонку.
Длина: 120-180 слов. Язык: русский. Обращайся к гонщику по имени."""


async def run_debriefs_after_race(race_id: int, season_id: int) -> None:
    if not _groq_api_key():
        print("[AI] GROQ_API_KEY not set, skipping debriefs")
        return

    engine = create_async_engine(get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    payloads: list[tuple[User, AICoachPayload]] = []
    race: Race | None = None

    try:
        async with session_factory() as db:
            race_result = await db.execute(select(Race).where(Race.id == race_id))
            race = race_result.scalars().first()
            if not race:
                return

            results_result = await db.execute(select(RaceResult).where(RaceResult.race_id == race_id))
            all_results = results_result.scalars().all()
            human_results = [item for item in all_results if item.is_human and item.user_id]
            if not human_results:
                return

            for result in human_results:
                player = await db.get(User, result.user_id)
                if not player:
                    continue
                payload = await _build_payload(db, player, result, race, all_results, season_id)
                payloads.append((player, payload))
    finally:
        await engine.dispose()

    for index, (player, payload) in enumerate(payloads):
        if index > 0:
            await asyncio.sleep(_stagger_sec())
        try:
            debrief = await _call_groq(payload)
            await _send_debrief(player, debrief, race)
        except Exception as exc:
            print(f"[AI] Debrief failed for {player.name}: {exc}")


async def _build_payload(
    db: AsyncSession,
    player: User,
    result: RaceResult,
    race: Race,
    all_results: list[RaceResult],
    season_id: int,
) -> AICoachPayload:
    from shared.f1_mappings import WEATHER

    payload = AICoachPayload()
    payload.player_name = player.name
    payload.driver_name = result.driver_name or "?"
    payload.team_name = result.team_name or "?"
    payload.track_name = race.track_name or "?"
    payload.position = result.position or 0
    payload.grid_position = result.grid_position or result.position or 0
    payload.total_players = len(all_results)
    payload.points_earned = result.points
    payload.result_status = _status_str(result.result_status)
    payload.best_lap_ms = result.best_lap_ms
    payload.has_fastest_lap = result.has_fastest_lap
    payload.penalties_sec = result.penalties_time or 0
    payload.num_penalties = result.num_penalties or 0
    payload.num_pit_stops = result.num_pit_stops or 0
    payload.tyre_stints = result.tyre_stints or []
    payload.weather = WEATHER.get(race.weather_start or 0, "Clear")
    payload.positions_gained = payload.grid_position - payload.position

    for other in all_results:
        if not other.is_human or other.vehicle_index == result.vehicle_index:
            continue
        if other.position and result.position and result.position < other.position:
            payload.beaten_players.append(other.driver_name or "?")
        elif other.position and result.position and result.position > other.position:
            payload.lost_to_players.append(other.driver_name or "?")

    season_result = await db.execute(
        select(RaceResult).where(
            RaceResult.user_id == player.id,
            RaceResult.season_id == season_id,
        )
    )
    season_results = season_result.scalars().all()
    positions = [item.position for item in season_results if item.position]

    payload.season_races = len(season_results)
    payload.season_points = sum(item.points for item in season_results)
    payload.season_wins = sum(1 for item in season_results if item.position == 1)
    payload.season_podiums = sum(1 for item in season_results if item.position and item.position <= 3)
    payload.season_dnfs = sum(1 for item in season_results if item.result_status in (4, 6))
    payload.season_avg_pos = sum(positions) / len(positions) if positions else 0
    return payload


def _status_str(status: int | None) -> str:
    mapping = {3: "Finished", 4: "DNF", 5: "DSQ", 6: "Retired"}
    return mapping.get(status or 3, "Unknown")


async def _call_groq(payload: AICoachPayload) -> str:
    request_body = {
        "model": _groq_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(payload)},
        ],
        "max_tokens": 400,
        "temperature": 0.75,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _groq_url(),
            json=request_body,
            headers={"Authorization": f"Bearer {_groq_api_key()}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def _send_debrief(player: User, debrief: str, race: Race | None) -> None:
    if not player.telegram_id or not race:
        return

    bot_url = os.getenv("BOT_NOTIFY_URL", "http://bot:8001/internal/race_uploaded")
    secret = os.getenv("BOT_NOTIFY_SECRET", "")
    notify_url = bot_url.replace("/internal/race_uploaded", "/internal/debrief")

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            notify_url,
            json={
                "telegram_id": player.telegram_id,
                "player_name": player.name,
                "track_name": race.track_name,
                "debrief": debrief,
            },
            headers={"X-Secret": secret},
        )
