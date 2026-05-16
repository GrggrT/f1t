"""
Маппинг steam_name → User из БД (бывший Player после Sprint 2 / PR 2.5).

Порядок поиска:
  1. Точное совпадение в steam_names[] (кэш)
  2. Fallback: резолвим текущий ник через Steam API по steam_id64
     → если совпало — обновляем кэш
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.models import User


async def find_player_by_steam_name(db: AsyncSession, steam_name: str) -> User | None:
    """Ищет пользователя у которого steam_name есть в массиве steam_names."""
    result = await db.execute(
        select(User).where(User.steam_names.any(steam_name))
    )
    return result.scalars().first()


async def find_player_by_steam_name_with_fallback(db: AsyncSession, steam_name: str) -> User | None:
    """
    Расширенный поиск:
    1. Проверяем кэш steam_names[]
    2. Если не найдено — для каждого пользователя с steam_id64 резолвим текущий ник
       через Steam XML API. Если совпало — обновляем кэш и возвращаем User.
    """
    user = await find_player_by_steam_name(db, steam_name)
    if user:
        return user

    from backend.services.steam_resolver import fetch_current_name

    result = await db.execute(
        select(User).where(User.steam_id64.isnot(None))
    )
    users_with_steam = result.scalars().all()

    for u in users_with_steam:
        current_name = await fetch_current_name(u.steam_id64)
        if current_name and current_name.lower() == steam_name.lower():
            names = list(u.steam_names or [])
            if steam_name not in names:
                names.append(steam_name)
                u.steam_names = names
                await db.commit()
            return u

    return None


async def add_steam_name(db: AsyncSession, user_id: int, steam_name: str) -> User | None:
    """Добавляет новое steam имя в историю пользователя."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        return None

    names = list(user.steam_names or [])
    if steam_name not in names:
        names.append(steam_name)
        user.steam_names = names
        await db.commit()
        await db.refresh(user)
    return user


async def resolve_participants(
    db: AsyncSession,
    participants: list[dict],
) -> tuple[dict[int, int], list[str]]:
    """
    Сопоставляет vehicle_index → user_id для всех human участников.
    Использует расширенный поиск с fallback через Steam API.

    Возвращает:
    - mapped: {vehicle_index: user_id}
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

        user = await find_player_by_steam_name_with_fallback(db, steam_name)
        if user:
            mapped[p["vehicle_index"]] = user.id
        else:
            unresolved.append(steam_name)

    return mapped, unresolved
