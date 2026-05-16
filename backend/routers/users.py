"""Sprint 2 / PR 2.2 — User-centric lookups.

Replaces parts of `players_admin.py` (/api/players/by_telegram) without
removing the old endpoint yet. The bot will switch to /api/users/* in
PR 2.3; old paths can be deleted in a later cleanup PR.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db
from backend.models.models import User


router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/by_telegram/{telegram_id}")
async def get_user_by_telegram(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Resolve a User by Telegram chat id.

    Returns the public identity used by the bot (`/stats`, `/standings`, etc).
    """
    user = (await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )).scalars().first()
    if not user:
        raise HTTPException(404, "User not registered")
    return {
        "id":               user.id,
        "name":             user.name,
        "telegram_id":      user.telegram_id,
        "steam_id64":       user.steam_id64,
        "steam_names":      list(user.steam_names) if user.steam_names else [],
        "avatar_url":       user.avatar_url,
        "is_system_admin":  user.is_system_admin,
        # Tracking columns kept until PR 2.5 so any debug tooling can join
        # back to the legacy tables if needed.
        "legacy_player_id":   user.legacy_player_id,
        "legacy_web_user_id": user.legacy_web_user_id,
    }
