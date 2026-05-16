"""Reusable auth dependencies for FastAPI endpoints."""
import os
import hmac
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from backend.db.base import get_db
from backend.models.models import User
from backend.services.jwt_auth import get_user_id_from_token


def _agent_secret_token() -> str:
    return os.getenv("AGENT_SECRET_TOKEN", "")


async def _resolve_user_from_token(uid: int, db: AsyncSession) -> User | None:
    """Look up a User by users.id, with fallback to legacy_web_user_id.

    New tokens (minted post-PR 2.5) carry `users.id` in `sub`. Older tokens
    still in flight carry the legacy `web_users.id`. Both work until the
    legacy_*_id columns are dropped in a future cosmetic migration.
    """
    return (await db.execute(
        select(User).where(or_(User.id == uid, User.legacy_web_user_id == uid))
    )).scalars().first()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate current user from JWT Bearer token. Raises 401 if invalid."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    uid = get_user_id_from_token(token)
    if not uid:
        raise HTTPException(401, "Authentication required")

    user = await _resolve_user_from_token(uid, db)
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same as get_current_user but returns None instead of raising 401."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    uid = get_user_id_from_token(token)
    if not uid:
        return None

    return await _resolve_user_from_token(uid, db)


def get_current_user_id(request: Request) -> int:
    """Lightweight: extract user_id from JWT without DB lookup. Raises 401."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    uid = get_user_id_from_token(token)
    if not uid:
        raise HTTPException(401, "Authentication required")
    return uid


def require_system_admin(user: User) -> User:
    """Check that user is a system admin. Raises 403 if not."""
    if not user.is_system_admin:
        raise HTTPException(403, "System admin access required")
    return user


async def verify_agent_token(request: Request) -> bool:
    """Verify agent token from header or query param.

    Fails closed: if AGENT_SECRET_TOKEN is not configured on the server,
    every agent-protected endpoint returns 503. The previous behavior
    silently allowed all agent calls when the env was missing, which is a
    Sprint 1 security regression we are explicitly closing here.

    Constant-time comparison via hmac.compare_digest prevents timing leaks.
    """
    secret = _agent_secret_token()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent authentication not configured. Set AGENT_SECRET_TOKEN.",
        )

    token = (
        request.headers.get("X-Agent-Token", "")
        or request.query_params.get("agent_token", "")
    )
    if not token:
        raise HTTPException(401, "Missing X-Agent-Token header")
    if not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Invalid agent token")
    return True
