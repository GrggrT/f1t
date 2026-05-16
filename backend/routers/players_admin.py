"""
Endpoints для регистрации игроков через Telegram бот.

После Sprint 2 / PR 2.5 «player» это просто `User` с заполненным
`telegram_id` и/или `steam_id64`. Таблицы `players` больше нет.

POST /api/players/register     — создать профиль (User c telegram_id)
POST /api/players/add_steam    — добавить Steam имя по telegram_id
POST /api/players/map_steam    — связать steam_name с user_id (после вопроса)
GET  /api/players              — список всех профилей-игроков
PATCH /api/players/{id}        — обновить имя / steam_names
GET  /api/players/by_telegram/{telegram_id}
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

import os
from backend.db.base import get_db
from backend.models.models import RaceResult, User
from backend.services.auth_helpers import require_system_admin_dep
from backend.services.player_mapper import add_steam_name
from backend.services.standings_service import recalc_standings

_SEASON_ID = int(os.getenv("F1_SEASON_ID", "1"))

router = APIRouter(prefix="/api/players", tags=["players_admin"])


class RegisterRequest(BaseModel):
    name:        str
    telegram_id: int | None = None

class AddSteamRequest(BaseModel):
    telegram_id: int
    steam_input: str   # URL, SteamID64, vanity name или просто ник

class MapSteamRequest(BaseModel):
    player_id:  int    # historical name; treated as users.id
    steam_name: str
    race_id:    int


@router.post("/register")
async def register_player(req: RegisterRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_system_admin_dep)):
    # Если telegram_id уже есть — возвращаем существующий профиль (идемпотентно)
    if req.telegram_id:
        existing_res = await db.execute(select(User).where(User.telegram_id == req.telegram_id))
        existing = existing_res.scalars().first()
        if existing:
            if req.name and req.name != existing.name:
                existing.name = req.name
                await db.commit()
                await db.refresh(existing)
            return {"id": existing.id, "name": existing.name, "already_exists": True}

    user = User(name=req.name, telegram_id=req.telegram_id, steam_names=[])
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "name": user.name, "already_exists": False}


@router.get("/by_telegram/{telegram_id}")
async def get_player_by_telegram(telegram_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "Not registered")
    return {"id": user.id, "name": user.name, "steam_names": user.steam_names}


@router.post("/add_steam")
async def add_steam_endpoint(req: AddSteamRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_system_admin_dep)):
    result = await db.execute(select(User).where(User.telegram_id == req.telegram_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "Player not found. Register first with /register")

    raw = req.steam_input.strip()

    # Если похоже на Steam ссылку — резолвим через Steam API
    if "steamcommunity.com" in raw or (raw.isdigit() and len(raw) == 17):
        from backend.services.steam_resolver import resolve_steam_profile
        info = await resolve_steam_profile(raw)
        if not info:
            raise HTTPException(400, "Не удалось получить данные Steam профиля. Проверь ссылку.")

        user.steam_id64  = info["steam_id64"]
        user.steam_url   = info["profile_url"]
        user.avatar_url  = info.get("avatar_url")
        await add_steam_name(db, user.id, info["persona_name"])
        await db.commit()
        await db.refresh(user)

        return {
            "id":           user.id,
            "name":         user.name,
            "steam_id64":   user.steam_id64,
            "steam_url":    user.steam_url,
            "persona_name": info["persona_name"],
            "steam_names":  user.steam_names,
            "resolved":     True,
        }

    # Иначе — просто ник из игры, добавляем напрямую
    updated = await add_steam_name(db, user.id, raw)
    return {
        "id":          user.id,
        "name":        user.name,
        "steam_names": updated.steam_names if updated else user.steam_names,
        "resolved":    False,
    }


@router.post("/map_steam")
async def map_steam(req: MapSteamRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_system_admin_dep)):
    """
    После того как бот спросил «кто такой X?» и пользователь выбрал —
    связываем steam_name с user_id и пересчитываем standing для этой гонки.
    """
    user_result = await db.execute(select(User).where(User.id == req.player_id))
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(404, "Player not found")

    await add_steam_name(db, req.player_id, req.steam_name)

    # Обновляем RaceResult где user_id == NULL и driver соответствует steam_name
    results_res = await db.execute(
        select(RaceResult).where(
            RaceResult.race_id == req.race_id,
            RaceResult.user_id == None,    # noqa: E711
            RaceResult.is_human == True,   # noqa: E712
        )
    )
    for rr in results_res.scalars().all():
        # Простая эвристика: если в гонке один неразмапленный human — это он
        rr.user_id = req.player_id

    await db.commit()

    # Пересчёт standings
    import asyncio
    asyncio.create_task(recalc_standings(_SEASON_ID))

    return {"ok": True, "player_name": user.name}


class UpdatePlayerRequest(BaseModel):
    name:        str | None = None
    steam_names: list[str] | None = None


@router.patch("/{player_id}")
async def update_player(player_id: int, req: UpdatePlayerRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_system_admin_dep)):
    result = await db.execute(select(User).where(User.id == player_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "Player not found")

    if req.name is not None:
        user.name = req.name.strip()
    if req.steam_names is not None:
        user.steam_names = [s.strip() for s in req.steam_names if s.strip()]

    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "name": user.name, "steam_names": user.steam_names}


@router.get("")
async def list_players(db: AsyncSession = Depends(get_db)):
    """List all User rows that represent a racing identity (have telegram_id or steam_id64)."""
    result = await db.execute(
        select(User)
        .where((User.telegram_id.isnot(None)) | (User.steam_id64.isnot(None)))
        .order_by(User.name)
    )
    users = result.scalars().all()
    return [{
        "id":          u.id,
        "name":        u.name,
        "telegram_id": u.telegram_id,
        "steam_id64":  u.steam_id64,
        "steam_url":   u.steam_url,
        "avatar_url":  u.avatar_url,
        "steam_names": u.steam_names,
    } for u in users]
