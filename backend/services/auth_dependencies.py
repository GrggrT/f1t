"""Reusable auth dependencies for FastAPI endpoints."""
import os
import hmac
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.base import get_db
from backend.models.models import WebUser
from backend.services.jwt_auth import get_user_id_from_token


def _agent_secret_token() -> str:
    return os.getenv("AGENT_SECRET_TOKEN", "")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebUser:
    """Extract and validate current user from JWT Bearer token. Raises 401 if invalid."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(401, "Authentication required")

    user = (await db.execute(
        select(WebUser).where(WebUser.id == user_id)
    )).scalars().first()

    if not user:
        raise HTTPException(401, "User not found")
    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebUser | None:
    """Same as get_current_user but returns None instead of raising 401."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    user_id = get_user_id_from_token(token)
    if not user_id:
        return None

    user = (await db.execute(
        select(WebUser).where(WebUser.id == user_id)
    )).scalars().first()
    return user


def get_current_user_id(request: Request) -> int:
    """Lightweight: extract user_id from JWT without DB lookup. Raises 401."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    uid = get_user_id_from_token(token)
    if not uid:
        raise HTTPException(401, "Authentication required")
    return uid


def require_system_admin(user: WebUser) -> WebUser:
    """Check that user is a system admin. Raises 403 if not."""
    if not user.is_system_admin:
        raise HTTPException(403, "System admin access required")
    return user


async def verify_agent_token(request: Request) -> bool:
    """Verify agent token from header or query param. Raises 401 if invalid."""
    secret = _agent_secret_token()
    if not secret:
        # If no token configured, allow (backward compatibility during migration)
        return True

    token = (
        request.headers.get("X-Agent-Token", "")
        or request.query_params.get("agent_token", "")
    )
    if not token or not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Invalid agent token")
    return True
