"""Role + scope dependencies for FastAPI endpoints.

Sits on top of backend.services.auth_dependencies. Use these whenever an
endpoint needs more than 'is authenticated' — e.g. system admin gate,
lobby-membership gate, or season-scoped lobby-moderator gate.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import get_db
from backend.models.models import Lobby, LobbyMember, Season, WebUser
from backend.services.auth_dependencies import get_current_user


async def require_system_admin_dep(
    user: WebUser = Depends(get_current_user),
) -> WebUser:
    """Authenticated AND `is_system_admin`. 401 if no token, 403 if not admin."""
    if not user.is_system_admin:
        raise HTTPException(403, "System admin access required")
    return user


async def require_lobby_member(
    lobby_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember | WebUser:
    """User must be a member (any role) of the lobby. 403 otherwise.

    System admins bypass — they have global read/write access by design.
    """
    if user.is_system_admin:
        return user
    member = await db.scalar(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == user.id,
        )
    )
    if not member:
        raise HTTPException(403, "Not a member of this lobby")
    return member


async def require_lobby_moderator(
    lobby_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember | WebUser:
    """User must be admin or moderator of the lobby. 403 otherwise.

    System admins bypass.
    """
    if user.is_system_admin:
        return user
    member = await require_lobby_member(lobby_id, user, db)
    if isinstance(member, WebUser):
        return member  # system_admin bypass already handled
    if member.role not in ("admin", "moderator"):
        raise HTTPException(403, "Moderator+ role required")
    return member


async def require_season_member(
    season_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember | WebUser:
    """User must be a member of the lobby that owns the given season.

    System admins bypass.
    Raises 404 if the season has no parent lobby (orphan — pre-lobby data).
    """
    if user.is_system_admin:
        return user
    season = await db.get(Season, season_id)
    if not season or not season.lobby_id:
        raise HTTPException(404, "Season not found")
    return await require_lobby_member(season.lobby_id, user, db)


async def require_season_moderator(
    season_id: int,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LobbyMember | WebUser:
    """Moderator+ of the lobby that owns the given season.

    System admins bypass.
    """
    if user.is_system_admin:
        return user
    season = await db.get(Season, season_id)
    if not season or not season.lobby_id:
        raise HTTPException(404, "Season not found")
    return await require_lobby_moderator(season.lobby_id, user, db)
