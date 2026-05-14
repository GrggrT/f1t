"""
Endpoints для регистрации игроков через Telegram бот.
POST /api/players/register     — создать профиль
POST /api/players/add_steam    — добавить Steam имя по telegram_id
POST /api/players/map_steam    — связать steam_name с player_id (после вопроса)
GET  /api/players              — список всех игроков
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

import os
from backend.db.base import get_db
from backend.models.models import Player, RaceResult, WebUser
from backend.services.auth_helpers import require_system_admin_dep
from backend.services.player_mapper import add_steam_name, find_player_by_steam_name
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
    player_id:  int
    steam_name: str
    race_id:    int


@router.post("/register")
async def register_player(req: RegisterRequest, db: AsyncSession = Depends(get_db), _: WebUser = Depends(require_system_admin_dep)):
    # Если telegram_id уже есть — возвращаем существующий профиль (идемпотентно)
    if req.telegram_id:
        existing_res = await db.execute(select(Player).where(Player.telegram_id == req.telegram_id))
        existing = existing_res.scalars().first()
        if existing:
            # Обновляем имя если передано новое
            if req.name and req.name != existing.name:
                existing.name = req.name
                await db.commit()
                await db.refresh(existing)
            return {"id": existing.id, "name": existing.name, "already_exists": True}

    player = Player(name=req.name, telegram_id=req.telegram_id, steam_names=[])
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return {"id": player.id, "name": player.name, "already_exists": False}


@router.get("/by_telegram/{telegram_id}")
async def get_player_by_telegram(telegram_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.telegram_id == telegram_id))
    player = result.scalars().first()
    if not player:
        raise HTTPException(404, "Not registered")
    return {"id": player.id, "name": player.name, "steam_names": player.steam_names}


@router.post("/add_steam")
async def add_steam_endpoint(req: AddSteamRequest, db: AsyncSession = Depends(get_db), _: WebUser = Depends(require_system_admin_dep)):
    result = await db.execute(select(Player).where(Player.telegram_id == req.telegram_id))
    player = result.scalars().first()
    if not player:
        raise HTTPException(404, "Player not found. Register first with /register")

    raw = req.steam_input.strip()

    # Определяем: это Steam URL/ID64/vanity или просто ник из игры
    is_steam_ref = (
        "steamcommunity.com" in raw
        or raw.isdigit()  # SteamID64
        or (len(raw) <= 32 and raw.replace("_", "").replace("-", "").isalnum() and len(raw) >= 3)
    )

    # Если похоже на Steam ссылку — резолвим через Steam API
    if "steamcommunity.com" in raw or (raw.isdigit() and len(raw) == 17):
        from backend.services.steam_resolver import resolve_steam_profile
        info = await resolve_steam_profile(raw)
        if not info:
            raise HTTPException(400, "Не удалось получить данные Steam профиля. Проверь ссылку.")

        # Сохраняем SteamID64, URL и текущий ник
        player.steam_id64  = info["steam_id64"]
        player.steam_url   = info["profile_url"]
        player.avatar_url  = info.get("avatar_url")
        await add_steam_name(db, player.id, info["persona_name"])
        await db.commit()
        await db.refresh(player)

        return {
            "id":           player.id,
            "name":         player.name,
            "steam_id64":   player.steam_id64,
            "steam_url":    player.steam_url,
            "persona_name": info["persona_name"],
            "steam_names":  player.steam_names,
            "resolved":     True,
        }

    # Иначе — просто ник из игры, добавляем напрямую
    updated = await add_steam_name(db, player.id, raw)
    return {
        "id":          player.id,
        "name":        player.name,
        "steam_names": updated.steam_names,
        "resolved":    False,
    }


@router.post("/map_steam")
async def map_steam(req: MapSteamRequest, db: AsyncSession = Depends(get_db), _: WebUser = Depends(require_system_admin_dep)):
    """
    После того как бот спросил «кто такой X?» и пользователь выбрал —
    связываем steam_name с player_id и пересчитываем standing для этой гонки.
    """
    player_result = await db.execute(select(Player).where(Player.id == req.player_id))
    player = player_result.scalars().first()
    if not player:
        raise HTTPException(404, "Player not found")

    # Добавляем steam_name в историю
    await add_steam_name(db, req.player_id, req.steam_name)

    # Обновляем RaceResult где player_id == NULL и driver соответствует steam_name
    # (ищем по steam_name в участниках гонки)
    results_res = await db.execute(
        select(RaceResult).where(
            RaceResult.race_id == req.race_id,
            RaceResult.player_id == None,  # noqa: E711
            RaceResult.is_human == True,   # noqa: E712
        )
    )
    for rr in results_res.scalars().all():
        # Простая эвристика: если в гонке один неразмапленный human — это он
        rr.player_id = req.player_id

    await db.commit()

    # Пересчёт standings
    import asyncio
    asyncio.create_task(recalc_standings(_SEASON_ID))

    return {"ok": True, "player_name": player.name}


class UpdatePlayerRequest(BaseModel):
    name:        str | None = None
    steam_names: list[str] | None = None


@router.patch("/{player_id}")
async def update_player(player_id: int, req: UpdatePlayerRequest, db: AsyncSession = Depends(get_db), _: WebUser = Depends(require_system_admin_dep)):
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalars().first()
    if not player:
        raise HTTPException(404, "Player not found")

    if req.name is not None:
        player.name = req.name.strip()
    if req.steam_names is not None:
        player.steam_names = [s.strip() for s in req.steam_names if s.strip()]

    await db.commit()
    await db.refresh(player)
    return {"id": player.id, "name": player.name, "steam_names": player.steam_names}


@router.get("")
async def list_players(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).order_by(Player.name))
    players = result.scalars().all()
    return [{
        "id":          p.id,
        "name":        p.name,
        "telegram_id": p.telegram_id,
        "steam_id64":  p.steam_id64,
        "steam_url":   p.steam_url,
        "avatar_url":  p.avatar_url,
        "steam_names": p.steam_names,
    } for p in players]
