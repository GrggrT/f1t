"""
Web auth endpoints — интеграция с NextAuth.js.

POST /api/web/register          — email + пароль регистрация
POST /api/web/login             — email + пароль → user dict
POST /api/web/google            — Google OAuth upsert
GET  /api/web/steam/start       — редирект на Steam OpenID
GET  /api/web/steam/callback    — верификация Steam OpenID
POST /api/web/steam-token       — обмен одноразового кода на user dict
GET  /api/web/me/{user_id}      — полный профиль + linked player
POST /api/web/link-player       — привязать WebUser к Player
"""
import os
import re
import time
import uuid

import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

SYSTEM_ADMIN_EMAILS = set(
    e.strip().lower()
    for e in os.getenv("SYSTEM_ADMIN_EMAILS", "gregorysky04i@gmail.com").split(",")
    if e.strip()
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.base import get_db
from backend.models.models import WebUser, Player
from backend.services.auth_dependencies import get_current_user
from backend.services.steam_resolver import resolve_steam_profile
from backend.services.jwt_auth import create_token, get_user_id_from_token

router = APIRouter(prefix="/api/web", tags=["web_auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL  = os.getenv("BACKEND_URL",  "http://localhost:8000")
STEAM_LOGIN  = "https://steamcommunity.com/openid/login"

# Одноразовые коды после Steam авторизации {code: {user_data, expires}}
# Limited to 1000 entries to prevent memory exhaustion
_steam_codes: dict[str, dict] = {}
_STEAM_CODES_MAX = 1000

# Launcher auth poll store {poll_id: {token, user_data, expires} | None}
# Limited to 1000 entries to prevent memory exhaustion
_launcher_polls: dict[str, dict | None] = {}
_LAUNCHER_POLLS_MAX = 1000


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def _verify(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def _to_dict(u: WebUser) -> dict:
    return {
        "id":              u.id,
        "email":           u.email,
        "name":            u.name,
        "picture":         u.picture,
        "google_id":       u.google_id,
        "steam_id64":      u.steam_id64,
        "player_id":       u.player_id,
        "is_system_admin": u.is_system_admin,
    }


# ── Email / password ──────────────────────────────────────────────────────────

class RegisterReq(BaseModel):
    email:    str
    password: str
    name:     str

class LoginReq(BaseModel):
    email:    str
    password: str

@router.post("/register")
async def web_register(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    # Validate email format
    email = req.email.lower().strip()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise HTTPException(400, "Invalid email format")

    # Validate password strength
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    exists = (await db.execute(
        select(WebUser).where(WebUser.email == email)
    )).scalars().first()
    if exists:
        raise HTTPException(409, "Email уже зарегистрирован")

    user = WebUser(
        email=email,
        name=req.name.strip(),
        hashed_password=_hash(req.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    result = _to_dict(user)
    result["token"] = create_token(user.id)
    return result


@router.post("/login")
async def web_login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(
        select(WebUser).where(WebUser.email == req.email.lower().strip())
    )).scalars().first()
    if not user or not user.hashed_password or not _verify(req.password, user.hashed_password):
        raise HTTPException(401, "Неверный email или пароль")
    result = _to_dict(user)
    result["token"] = create_token(user.id)
    return result


@router.post("/launcher/login")
async def launcher_login(req: LoginReq, db: AsyncSession = Depends(get_db)):
    """Login from launcher — returns user + JWT token."""
    user = (await db.execute(
        select(WebUser).where(WebUser.email == req.email.lower().strip())
    )).scalars().first()
    if not user or not user.hashed_password or not _verify(req.password, user.hashed_password):
        raise HTTPException(401, "Неверный email или пароль")
    result = _to_dict(user)
    result["token"] = create_token(user.id)
    return result


@router.get("/me/by-token")
async def me_by_token(request: Request, db: AsyncSession = Depends(get_db)):
    """Get user profile from JWT token (Authorization header)."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(401, "Invalid or expired token")
    user = (await db.execute(
        select(WebUser).where(WebUser.id == user_id)
    )).scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    data = _to_dict(user)
    if user.player_id:
        player = (await db.execute(
            select(Player).where(Player.id == user.player_id)
        )).scalars().first()
        if player:
            data["player"] = {
                "id": player.id,
                "name": player.name,
                "steam_id64": player.steam_id64,
                "avatar_url": player.avatar_url,
            }
    return data


# ── Google OAuth ──────────────────────────────────────────────────────────────

class GoogleReq(BaseModel):
    google_id: str
    email:     str | None = None
    name:      str
    picture:   str | None = None

@router.post("/google")
async def web_google(req: GoogleReq, db: AsyncSession = Depends(get_db)):
    # Ищем по google_id
    user = (await db.execute(
        select(WebUser).where(WebUser.google_id == req.google_id)
    )).scalars().first()

    # Или по email (объединяем аккаунты)
    if not user and req.email:
        user = (await db.execute(
            select(WebUser).where(WebUser.email == req.email.lower())
        )).scalars().first()

    if user:
        user.google_id = req.google_id
        if req.picture and not user.picture:
            user.picture = req.picture
    else:
        email_lower = req.email.lower() if req.email else None
        user = WebUser(
            google_id=req.google_id,
            email=email_lower,
            name=req.name,
            picture=req.picture,
            is_system_admin=email_lower in SYSTEM_ADMIN_EMAILS if email_lower else False,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Автопривязка к Player по steam_id64
    if not user.player_id and user.steam_id64:
        p = (await db.execute(
            select(Player).where(Player.steam_id64 == user.steam_id64)
        )).scalars().first()
        if p:
            user.player_id = p.id
            await db.commit()
            await db.refresh(user)

    result = _to_dict(user)
    result["token"] = create_token(user.id)
    return result


# ── Steam OpenID 2.0 ──────────────────────────────────────────────────────────

@router.get("/steam/start")
async def steam_start():
    """Редирект на Steam OpenID."""
    callback = f"{BACKEND_URL}/api/web/steam/callback"
    params = "&".join([
        "openid.ns=http://specs.openid.net/auth/2.0",
        "openid.mode=checkid_setup",
        f"openid.return_to={callback}",
        f"openid.realm={BACKEND_URL}",
        "openid.identity=http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select",
    ])
    return RedirectResponse(f"{STEAM_LOGIN}?{params}")


@router.get("/steam/callback")
async def steam_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Steam возвращает пользователя сюда после авторизации."""
    params = dict(request.query_params)

    # Верифицируем с Steam
    verify = {**params, "openid.mode": "check_authentication"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(STEAM_LOGIN, data=verify)
        if "is_valid:true" not in r.text:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=steam_invalid")
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=steam_error")

    # Извлекаем SteamID64 из claimed_id
    claimed = params.get("openid.claimed_id", "")
    match = re.search(r"/openid/id/(\d+)$", claimed)
    if not match:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=steam_id")
    steam_id64 = match.group(1)

    # Получаем имя и аватар
    info = await resolve_steam_profile(steam_id64)
    name   = info["persona_name"] if info else f"Steam_{steam_id64[-4:]}"
    avatar = info.get("avatar_url") if info else None

    # Ищем или создаём WebUser
    user = (await db.execute(
        select(WebUser).where(WebUser.steam_id64 == steam_id64)
    )).scalars().first()

    if not user:
        # Автопривязка к Player если совпадает steam_id64
        player = (await db.execute(
            select(Player).where(Player.steam_id64 == steam_id64)
        )).scalars().first()
        user = WebUser(
            steam_id64=steam_id64,
            name=name,
            picture=avatar,
            player_id=player.id if player else None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        if avatar and not user.picture:
            user.picture = avatar
            await db.commit()

    # Одноразовый код для NextAuth Credentials
    code = str(uuid.uuid4())
    now  = time.time()
    # Чистим протухшие + enforce limit
    for k in [k for k, v in list(_steam_codes.items()) if v["expires"] < now]:
        del _steam_codes[k]
    if len(_steam_codes) >= _STEAM_CODES_MAX:
        oldest = min(_steam_codes, key=lambda k: _steam_codes[k]["expires"])
        del _steam_codes[oldest]
    _steam_codes[code] = {**_to_dict(user), "token": create_token(user.id), "expires": now + 120}

    return RedirectResponse(f"{FRONTEND_URL}/login?steam_token={code}")


class SteamTokenReq(BaseModel):
    token: str

@router.post("/steam-token")
async def steam_token_exchange(req: SteamTokenReq):
    """NextAuth Credentials вызывает это чтобы обменять код на user dict."""
    data = _steam_codes.get(req.token)
    if not data or data["expires"] < time.time():
        _steam_codes.pop(req.token, None)
        raise HTTPException(401, "Steam токен недействителен или истёк")
    del _steam_codes[req.token]
    return data


# ── Me / Link ─────────────────────────────────────────────────────────────────

@router.get("/me/{user_id}")
async def web_me(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    # Allow access only to own profile or via valid auth
    from backend.services.auth_dependencies import get_current_user_optional
    auth_user = await get_current_user_optional(request, db)

    # If authenticated, allow access to own profile; system admin can view any
    if auth_user and auth_user.id != user_id and not auth_user.is_system_admin:
        raise HTTPException(403, "Access denied")

    user = (await db.execute(
        select(WebUser).where(WebUser.id == user_id)
    )).scalars().first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    data = _to_dict(user)

    # Hide sensitive fields from non-owner requests
    if not auth_user or auth_user.id != user_id:
        data.pop("is_system_admin", None)

    if user.player_id:
        player = (await db.execute(
            select(Player).where(Player.id == user.player_id)
        )).scalars().first()
        if player:
            data["player"] = {
                "id":          player.id,
                "name":        player.name,
                "steam_url":   player.steam_url,
                "steam_id64":  player.steam_id64,
                "steam_names": player.steam_names,
                "telegram_id": player.telegram_id,
                "avatar_url":  player.avatar_url,
            }

    return data


class LinkPlayerReq(BaseModel):
    player_id: int

@router.post("/link-player")
async def link_player(
    req: LinkPlayerReq,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bind the caller's WebUser to a Player row.

    Ownership check: the dependency injects the WebUser from the Bearer
    token, and we only ever mutate that user's player_id — so there is
    no way to link another user's account.
    """
    player = (await db.execute(
        select(Player).where(Player.id == req.player_id)
    )).scalars().first()
    if not player:
        raise HTTPException(404, "Игрок не найден")

    user.player_id = req.player_id
    if user.picture and not player.avatar_url:
        player.avatar_url = user.picture
    await db.commit()
    return {"ok": True, "player_name": player.name}


# ── Launcher Poll Auth (Google login via browser) ─────────────────────────────

class LauncherAuthReq(BaseModel):
    poll_id: str

@router.post("/launcher/auth")
async def launcher_auth_complete(
    req: LauncherAuthReq,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Website calls this after user logs in, to provide token to launcher."""
    token = create_token(user.id)
    result = _to_dict(user)
    result["token"] = token
    # Clean expired + enforce limit
    now = time.time()
    for k in [k for k, v in list(_launcher_polls.items()) if v and v.get("_expires", 0) < now]:
        del _launcher_polls[k]
    if len(_launcher_polls) >= _LAUNCHER_POLLS_MAX:
        oldest = min(_launcher_polls, key=lambda k: (_launcher_polls[k] or {}).get("_expires", 0))
        del _launcher_polls[oldest]
    _launcher_polls[req.poll_id] = {**result, "_expires": time.time() + 300}
    return {"ok": True}


@router.get("/launcher/poll/{poll_id}")
async def launcher_poll(poll_id: str):
    """Launcher polls this to check if user completed Google login."""
    data = _launcher_polls.get(poll_id)
    if not data:
        raise HTTPException(404, "Not ready")
    if data.get("_expires", 0) < time.time():
        del _launcher_polls[poll_id]
        raise HTTPException(410, "Expired")
    del _launcher_polls[poll_id]
    data.pop("_expires", None)
    return data
