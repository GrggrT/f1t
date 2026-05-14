"""
Маппинг steam_name → player из БД.
Порядок поиска:
  1. Точное совпадение в steam_names[] (кэш)
  2. Fallback: резолвим текущий ник через Steam API по steam_id64
     → если совпало — обновляем кэш
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.models import Player


async def find_player_by_steam_name(db: AsyncSession, steam_name: str) -> Player | None:
    """Ищет игрока у которого steam_name есть в массиве steam_names."""
    result = await db.execute(
        select(Player).where(Player.steam_names.any(steam_name))
    )
    return result.scalars().first()


async def find_player_by_steam_name_with_fallback(db: AsyncSession, steam_name: str) -> Player | None:
    """
    Расширенный поиск:
    1. Проверяем кэш steam_names[]
    2. Если не найдено — для каждого игрока с steam_id64 резолвим текущий ник
       через Steam XML API. Если совпало — обновляем кэш и возвращаем игрока.
    """
    # Быстрый путь — кэш
    player = await find_player_by_steam_name(db, steam_name)
    if player:
        return player

    # Fallback — проверяем актуальный ник через Steam
    from backend.services.steam_resolver import fetch_current_name

    result = await db.execute(
        select(Player).where(Player.steam_id64.isnot(None))
    )
    players_with_steam = result.scalars().all()

    for p in players_with_steam:
        current_name = await fetch_current_name(p.steam_id64)
        if current_name and current_name.lower() == steam_name.lower():
            # Имя совпало — обновляем кэш чтобы следующий раз не делать запрос
            names = list(p.steam_names or [])
            if steam_name not in names:
                names.append(steam_name)
                p.steam_names = names
                await db.commit()
            return p

    return None


async def add_steam_name(db: AsyncSession, player_id: int, steam_name: str) -> Player | None:
    """Добавляет новое steam имя в историю игрока."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalars().first()
    if not player:
        return None

    names = list(player.steam_names or [])
    if steam_name not in names:
        names.append(steam_name)
        player.steam_names = names
        await db.commit()
        await db.refresh(player)
    return player


async def resolve_participants(
    db: AsyncSession,
    participants: list[dict],
) -> tuple[dict[int, int], list[str]]:
    """
    Сопоставляет vehicle_index → player_id для всех human участников.
    Использует расширенный поиск с fallback через Steam API.

    Возвращает:
    - mapped: {vehicle_index: player_id}
    - unresolved: список steam_name которые не нашлись
    """
    mapped: dict[int, int] = {}
    unresolved: list[str] = []

    for p in participants:
        if not p.get("m_aiControlled") == 0:
            continue  # бот, пропускаем

        steam_name = p.get("m_name", "").strip()
        if not steam_name:
            continue

        player = await find_player_by_steam_name_with_fallback(db, steam_name)
        if player:
            mapped[p["vehicle_index"]] = player.id
        else:
            unresolved.append(steam_name)

    return mapped, unresolved
