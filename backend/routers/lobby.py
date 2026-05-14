"""
Lobby management — CRUD, invite system, members, seasons within lobby.

GET    /api/lobby                          — list lobbies for current user (or all public)
POST   /api/lobby                          — create lobby
GET    /api/lobby/{id}                     — lobby info + role
POST   /api/lobby/{id}/join               — join via invite code
DELETE /api/lobby/{id}/leave               — leave lobby
GET    /api/lobby/{id}/members             — list members
PATCH  /api/lobby/{id}/members/{uid}/role  — change member role (admin only)
DELETE /api/lobby/{id}/members/{uid}       — kick member (admin/mod)
PUT    /api/lobby/{id}/settings            — update name/description (admin/mod)
POST   /api/lobby/{id}/invite/reset        — regenerate invite code (admin)
POST   /api/lobby/{id}/seasons             — create season within lobby (admin/mod)
GET    /api/lobby/{id}/seasons             — list seasons in lobby
GET    /api/lobby/{id}/engineer            — AI engineer context
POST   /api/lobby/{id}/engineer/ask        — ask AI engineer
"""
import os
import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.base import get_db
from backend.services.auth_dependencies import get_current_user, get_current_user_optional
from backend.models.models import (
    Lobby, LobbyMember, Season, WebUser, Player,
    Race, RaceResult, ChampionshipStanding,
)

router = APIRouter(prefix="/api/lobby", tags=["lobby"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_lobby_or_404(lobby_id: int, db: AsyncSession) -> Lobby:
    lobby = await db.get(Lobby, lobby_id)
    if not lobby:
        raise HTTPException(404, "Lobby not found")
    return lobby


async def _get_member_role(lobby_id: int, web_user_id: int | None, db: AsyncSession) -> str:
    """Returns 'admin' | 'moderator' | 'member' | 'guest'."""
    if not web_user_id:
        return "guest"
    res = await db.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == web_user_id,
        )
    )
    member = res.scalars().first()
    return member.role if member else "guest"


def _require_role(role: str, min_role: str):
    order = {"guest": 0, "member": 1, "moderator": 2, "admin": 3}
    if order.get(role, 0) < order.get(min_role, 99):
        raise HTTPException(403, f"Requires at least {min_role} role")


# ── Lobby CRUD ────────────────────────────────────────────────────────────────

class CreateLobbyReq(BaseModel):
    name:        str
    description: str | None = None


@router.post("")
async def create_lobby(req: CreateLobbyReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a new lobby. Creator becomes admin member."""
    lobby = Lobby(
        name=req.name,
        description=req.description,
        creator_id=user.id,
        invite_code=secrets.token_urlsafe(8),
    )
    db.add(lobby)
    await db.flush()

    db.add(LobbyMember(
        lobby_id=lobby.id,
        web_user_id=user.id,
        role="admin",
    ))
    await db.commit()
    await db.refresh(lobby)

    return {
        "id":          lobby.id,
        "name":        lobby.name,
        "description": lobby.description,
        "invite_code": lobby.invite_code,
        "created_at":  lobby.created_at.isoformat() if lobby.created_at else None,
    }


@router.get("")
async def list_lobbies(web_user_id: int | None = None, user: WebUser | None = Depends(get_current_user_optional), db: AsyncSession = Depends(get_db)):
    """List lobbies. If authenticated — their lobbies, else all."""
    effective_user_id = user.id if user else web_user_id
    if effective_user_id:
        res = await db.execute(
            select(Lobby, LobbyMember.role)
            .join(LobbyMember, LobbyMember.lobby_id == Lobby.id)
            .where(LobbyMember.web_user_id == effective_user_id)
            .order_by(Lobby.created_at.desc())
        )
        rows = res.all()
        out = []
        for lobby, role in rows:
            season_cnt = await db.execute(
                select(func.count()).select_from(Season).where(Season.lobby_id == lobby.id)
            )
            member_cnt = await db.execute(
                select(func.count()).select_from(LobbyMember).where(LobbyMember.lobby_id == lobby.id)
            )
            out.append({
                "id":          lobby.id,
                "name":        lobby.name,
                "description": lobby.description,
                "avatar_url":  lobby.avatar_url,
                "your_role":   role,
                "members":     member_cnt.scalar() or 0,
                "seasons":     season_cnt.scalar() or 0,
                "created_at":  lobby.created_at.isoformat() if lobby.created_at else None,
            })
        return out
    else:
        res = await db.execute(select(Lobby).order_by(Lobby.created_at.desc()))
        lobbies = res.scalars().all()
        out = []
        for lobby in lobbies:
            season_cnt = await db.execute(
                select(func.count()).select_from(Season).where(Season.lobby_id == lobby.id)
            )
            member_cnt = await db.execute(
                select(func.count()).select_from(LobbyMember).where(LobbyMember.lobby_id == lobby.id)
            )
            out.append({
                "id":          lobby.id,
                "name":        lobby.name,
                "description": lobby.description,
                "avatar_url":  lobby.avatar_url,
                "members":     member_cnt.scalar() or 0,
                "seasons":     season_cnt.scalar() or 0,
                "created_at":  lobby.created_at.isoformat() if lobby.created_at else None,
            })
        return out


@router.get("/host-seasons")
async def list_host_seasons(user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Flatten lobby seasons the current user can realistically target from launcher host mode."""
    res = await db.execute(
        select(Season, Lobby, LobbyMember.role)
        .join(Lobby, Season.lobby_id == Lobby.id)
        .join(
            LobbyMember,
            (LobbyMember.lobby_id == Lobby.id) & (LobbyMember.web_user_id == user.id),
        )
        .order_by(Season.created_at.desc(), Season.id.desc())
    )
    rows = res.all()

    out = []
    for season, lobby, role in rows:
        race_cnt = await db.execute(
            select(func.count()).select_from(Race).where(Race.season_id == season.id)
        )
        out.append({
            "id": season.id,
            "name": season.name,
            "status": season.status,
            "races_played": race_cnt.scalar() or 0,
            "total_rounds": len(season.calendar) if isinstance(season.calendar, list) else 0,
            "created_at": season.created_at.isoformat() if season.created_at else None,
            "lobby_id": lobby.id,
            "lobby_name": lobby.name,
            "lobby_description": lobby.description,
            "role": role,
            "can_manage": role in ("admin", "moderator"),
        })

    status_rank = {"active": 0, "completed": 1, "archived": 2}
    out.sort(
        key=lambda item: (
            status_rank.get(item.get("status") or "active", 99),
            -(item.get("id") or 0),
        )
    )
    return out


@router.get("/{lobby_id}")
async def get_lobby(lobby_id: int, web_user_id: int | None = None, user: WebUser | None = Depends(get_current_user_optional), db: AsyncSession = Depends(get_db)):
    """Lobby detail + current user's role."""
    lobby = await _get_lobby_or_404(lobby_id, db)
    effective_user_id = user.id if user else web_user_id
    role = await _get_member_role(lobby_id, effective_user_id, db)

    creator = await db.get(WebUser, lobby.creator_id)
    member_cnt = await db.execute(
        select(func.count()).select_from(LobbyMember).where(LobbyMember.lobby_id == lobby_id)
    )

    # Seasons in this lobby
    seasons_res = await db.execute(
        select(Season).where(Season.lobby_id == lobby_id).order_by(Season.id.desc())
    )
    seasons = seasons_res.scalars().all()
    seasons_data = []
    for s in seasons:
        race_cnt = await db.execute(
            select(func.count()).select_from(Race).where(Race.season_id == s.id)
        )
        seasons_data.append({
            "id":           s.id,
            "name":         s.name,
            "status":       s.status,
            "races_played": race_cnt.scalar() or 0,
            "total_rounds": len(s.calendar) if isinstance(s.calendar, list) else 0,
        })

    return {
        "id":           lobby.id,
        "name":         lobby.name,
        "description":  lobby.description,
        "avatar_url":   lobby.avatar_url,
        "creator_id":   lobby.creator_id,
        "creator_name": creator.name if creator else None,
        "invite_code":  lobby.invite_code if role in ("admin", "moderator") else None,
        "members_count": member_cnt.scalar() or 0,
        "seasons":      seasons_data,
        "your_role":    role,
        "can_manage":   role in ("admin", "moderator"),
        "can_create_season": role in ("admin", "moderator"),
        "can_reset_invite": role == "admin",
        "created_at":   lobby.created_at.isoformat() if lobby.created_at else None,
    }


# ── Join / Leave ──────────────────────────────────────────────────────────────

class JoinReq(BaseModel):
    invite_code: str


@router.post("/{lobby_id}/join")
async def join_lobby(lobby_id: int, req: JoinReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Join lobby using invite code."""
    lobby = await _get_lobby_or_404(lobby_id, db)
    if lobby.invite_code != req.invite_code:
        raise HTTPException(403, "Invalid invite code")

    existing = await db.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == user.id,
        )
    )
    if existing.scalars().first():
        return {"ok": True, "message": "Already a member"}

    db.add(LobbyMember(lobby_id=lobby_id, web_user_id=user.id, role="member"))
    await db.commit()
    return {"ok": True, "message": f"Joined '{lobby.name}'"}


@router.post("/join-by-code")
async def join_by_code(req: JoinReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Join lobby using only invite code (no lobby_id needed)."""
    res = await db.execute(
        select(Lobby).where(Lobby.invite_code == req.invite_code)
    )
    lobby = res.scalars().first()
    if not lobby:
        raise HTTPException(404, "Invalid invite code")

    existing = await db.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby.id,
            LobbyMember.web_user_id == user.id,
        )
    )
    if existing.scalars().first():
        return {"ok": True, "lobby_id": lobby.id, "message": "Already a member"}

    db.add(LobbyMember(lobby_id=lobby.id, web_user_id=user.id, role="member"))
    await db.commit()
    return {"ok": True, "lobby_id": lobby.id, "message": f"Joined '{lobby.name}'"}


@router.delete("/{lobby_id}/leave")
async def leave_lobby(lobby_id: int, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Leave lobby. Admin cannot leave (must transfer ownership first)."""
    lobby = await _get_lobby_or_404(lobby_id, db)
    if lobby.creator_id == user.id:
        raise HTTPException(400, "Admin cannot leave. Transfer ownership first.")

    res = await db.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == user.id,
        )
    )
    member = res.scalars().first()
    if member:
        await db.delete(member)
        await db.commit()
    return {"ok": True}


# ── Members ───────────────────────────────────────────────────────────────────

@router.get("/{lobby_id}/members")
async def list_members(lobby_id: int, db: AsyncSession = Depends(get_db)):
    await _get_lobby_or_404(lobby_id, db)
    res = await db.execute(
        select(LobbyMember, WebUser.name.label("uname"), WebUser.picture.label("upic"))
        .join(WebUser, LobbyMember.web_user_id == WebUser.id)
        .where(LobbyMember.lobby_id == lobby_id)
        .order_by(LobbyMember.role.desc(), LobbyMember.joined_at)
    )
    return [
        {
            "web_user_id": row.LobbyMember.web_user_id,
            "name":        row.uname,
            "picture":     row.upic,
            "role":        row.LobbyMember.role,
            "joined_at":   row.LobbyMember.joined_at.isoformat() if row.LobbyMember.joined_at else None,
        }
        for row in res.all()
    ]


class RoleChangeReq(BaseModel):
    new_role: str   # moderator / member


@router.patch("/{lobby_id}/members/{uid}/role")
async def change_member_role(lobby_id: int, uid: int, req: RoleChangeReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await _get_member_role(lobby_id, user.id, db)
    _require_role(role, "admin")

    if req.new_role not in ("moderator", "member"):
        raise HTTPException(400, "Role must be 'moderator' or 'member'")

    lobby = await db.get(Lobby, lobby_id)
    if lobby.creator_id == uid:
        raise HTTPException(400, "Cannot change admin's role")

    res = await db.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == uid,
        )
    )
    member = res.scalars().first()
    if not member:
        raise HTTPException(404, "Member not found")

    member.role = req.new_role
    await db.commit()
    return {"ok": True, "role": req.new_role}


@router.delete("/{lobby_id}/members/{uid}")
async def kick_member(lobby_id: int, uid: int, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await _get_member_role(lobby_id, user.id, db)
    _require_role(role, "moderator")

    lobby = await db.get(Lobby, lobby_id)
    if lobby.creator_id == uid:
        raise HTTPException(400, "Cannot kick the lobby creator")

    res = await db.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.web_user_id == uid,
        )
    )
    member = res.scalars().first()
    if member:
        await db.delete(member)
        await db.commit()
    return {"ok": True}


# ── Settings ──────────────────────────────────────────────────────────────────

class LobbySettingsReq(BaseModel):
    name:        str | None = None
    description: str | None = None


@router.put("/{lobby_id}/settings")
async def update_settings(lobby_id: int, req: LobbySettingsReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await _get_member_role(lobby_id, user.id, db)
    _require_role(role, "moderator")
    lobby = await _get_lobby_or_404(lobby_id, db)
    if req.name is not None:
        lobby.name = req.name
    if req.description is not None:
        lobby.description = req.description
    await db.commit()
    return {"ok": True, "name": lobby.name, "description": lobby.description}


@router.post("/{lobby_id}/invite/reset")
async def reset_invite_code(lobby_id: int, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await _get_member_role(lobby_id, user.id, db)
    _require_role(role, "admin")
    lobby = await _get_lobby_or_404(lobby_id, db)
    lobby.invite_code = secrets.token_urlsafe(8)
    await db.commit()
    return {"ok": True, "invite_code": lobby.invite_code}


# ── Seasons within Lobby ──────────────────────────────────────────────────────

class CreateSeasonReq(BaseModel):
    name: str


@router.post("/{lobby_id}/seasons")
async def create_season(lobby_id: int, req: CreateSeasonReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a new season within this lobby."""
    role = await _get_member_role(lobby_id, user.id, db)
    _require_role(role, "moderator")

    season = Season(
        name=req.name,
        status="active",
        calendar=[],
        points_system={},
        creator_id=user.id,
        lobby_id=lobby_id,
    )
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return {
        "id":       season.id,
        "name":     season.name,
        "lobby_id": lobby_id,
        "status":   season.status,
    }


@router.get("/{lobby_id}/seasons")
async def list_lobby_seasons(lobby_id: int, db: AsyncSession = Depends(get_db)):
    await _get_lobby_or_404(lobby_id, db)
    res = await db.execute(
        select(Season).where(Season.lobby_id == lobby_id).order_by(Season.id.desc())
    )
    seasons = res.scalars().all()
    out = []
    for s in seasons:
        race_cnt = await db.execute(
            select(func.count()).select_from(Race).where(Race.season_id == s.id)
        )
        out.append({
            "id":           s.id,
            "name":         s.name,
            "status":       s.status,
            "races_played": race_cnt.scalar() or 0,
            "total_rounds": len(s.calendar) if isinstance(s.calendar, list) else 0,
            "created_at":   s.created_at.isoformat() if s.created_at else None,
        })
    return out


# ── AI Engineer (per lobby) ──────────────────────────────────────────────────

@router.get("/{lobby_id}/engineer")
async def get_engineer_context(
    lobby_id:  int,
    season_id: int | None = None,
    user: WebUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pilot context for AI engineer. Optional season_id to scope data."""
    await _get_lobby_or_404(lobby_id, db)
    if not user.player_id:
        raise HTTPException(400, "No linked player profile")

    player = await db.get(Player, user.player_id)

    # Get seasons in this lobby
    lobby_seasons = await db.execute(
        select(Season.id).where(Season.lobby_id == lobby_id)
    )
    season_ids = [r[0] for r in lobby_seasons.all()]
    if season_id and season_id in season_ids:
        season_ids = [season_id]

    if not season_ids:
        return {"player_name": player.name if player else user.name, "race_history": []}

    # Standings
    standing_res = await db.execute(
        select(ChampionshipStanding).where(
            ChampionshipStanding.season_id.in_(season_ids),
            ChampionshipStanding.player_id == user.player_id,
        )
    )
    standing = standing_res.scalars().first()

    # Race results
    results_res = await db.execute(
        select(RaceResult, Race.track_name, Race.round_number)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            RaceResult.player_id == user.player_id,
            Race.season_id.in_(season_ids),
        )
        .order_by(Race.round_number)
    )
    results = results_res.all()

    race_data = [
        {
            "round":       r,
            "track":       t,
            "position":    rr.position,
            "points":      rr.points,
            "fastest_lap": rr.has_fastest_lap,
            "status":      rr.result_status,
        }
        for rr, t, r in results
    ]

    return {
        "player_name":  player.name if player else user.name,
        "player_id":    user.player_id,
        "lobby_id":     lobby_id,
        "position":     standing.position if standing else None,
        "total_points": standing.total_points if standing else 0,
        "wins":         standing.wins if standing else 0,
        "podiums":      standing.podiums if standing else 0,
        "dnfs":         standing.dnfs if standing else 0,
        "fastest_laps": standing.fastest_laps if standing else 0,
        "races_played": len(results),
        "race_history": race_data,
    }


class EngineerAskReq(BaseModel):
    question:  str
    season_id: int | None = None


@router.post("/{lobby_id}/engineer/ask")
async def ask_engineer(lobby_id: int, req: EngineerAskReq, user: WebUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """AI engineer: works with lobby's season data."""
    await _get_lobby_or_404(lobby_id, db)
    if not user.player_id:
        raise HTTPException(400, "No linked player profile")

    player = await db.get(Player, user.player_id)

    # Get seasons in this lobby
    lobby_seasons = await db.execute(
        select(Season).where(Season.lobby_id == lobby_id)
    )
    all_seasons = lobby_seasons.scalars().all()
    season_ids = [s.id for s in all_seasons]
    if req.season_id and req.season_id in season_ids:
        season_ids = [req.season_id]

    results_res = await db.execute(
        select(RaceResult, Race.track_name, Race.season_id)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            RaceResult.player_id == user.player_id,
            Race.season_id.in_(season_ids),
        )
        .order_by(Race.season_id, Race.round_number)
    )
    results = results_res.all()

    if not results:
        return {"answer": "У тебя пока нет данных. Сыграй хотя бы одну гонку!"}

    total_races = len(results)
    wins        = sum(1 for rr, _, _ in results if rr.position == 1)
    podiums     = sum(1 for rr, _, _ in results if rr.position and rr.position <= 3)
    dnfs        = sum(1 for rr, _, _ in results if rr.result_status not in ("Finished", "finished", 0, 1))
    points      = sum(rr.points for rr, _, _ in results)
    positions   = [rr.position for rr, _, _ in results if rr.position]
    avg_pos     = sum(positions) / len(positions) if positions else 0

    race_lines = [
        f"R{i+1} {t}: P{rr.position or 'DNF'} {rr.points}pts"
        for i, (rr, t, _) in enumerate(results[-8:])
    ]

    lobby = await db.get(Lobby, lobby_id)
    context = (
        f"Пилот: {player.name} | Лобби: {lobby.name}\n"
        f"Гонок: {total_races} | Победы: {wins} | Подиумы: {podiums} | DNF: {dnfs}\n"
        f"Очки: {points} | Средняя позиция: {avg_pos:.1f}\n"
        f"Последние гонки: {' | '.join(race_lines)}"
    )

    if not GROQ_API_KEY:
        return {"answer": "AI недоступен: GROQ_API_KEY не настроен."}

    import httpx
    system_prompt = (
        "Ты — гоночный инженер Формулы 1 мирового уровня. Твои образцы для подражания — "
        "Питер 'Боно' Боннингтон (инженер Хэмилтона) и Джанпьеро Ламбьязе (инженер Ферстаппена).\n\n"
        "## Стиль общения\n"
        "- Говори как настоящий инженер по рации: спокойно, точно, уверенно\n"
        "- Используй характерные фразы: 'Копирую', 'Понял тебя', 'Хорошая работа', "
        "'Так, слушай...', 'Давай сфокусируемся на...'\n"
        "- Будь конкретным: указывай номера кругов, позиции, разрывы в секундах\n"
        "- Когда данные показывают проблемы — будь честным, но конструктивным. "
        "Никогда не вини пилота, предлагай решения\n"
        "- Подбадривай когда уместно: 'Темп отличный', 'Чистая работа', "
        "'Ты в хорошей форме сегодня'\n\n"
        "## Твои компетенции\n"
        "- Анализ результатов: тренды, прогресс, слабые/сильные трассы\n"
        "- Стратегия: когда атаковать, когда беречь резину, когда рисковать\n"
        "- Сравнение с соперниками: где пилот выигрывает и проигрывает\n"
        "- Рекомендации по подготовке к следующей гонке\n"
        "- Психологическая поддержка: помощь после неудачных гонок\n\n"
        "## Правила\n"
        "- Отвечай строго по-русски\n"
        "- Держи ответы до 200 слов, если не просят детальный разбор\n"
        "- Используй **жирный** для ключевых данных и `код` для времён/цифр\n"
        "- Если данных мало — скажи что нужно больше гонок для точного анализа, "
        "но всё равно дай совет на основе того что есть"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model":    GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": f"Данные:\n{context}\n\nВопрос: {req.question}"},
                    ],
                    "max_tokens":  500,
                    "temperature": 0.7,
                },
            )
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ENGINEER] Error: {e}")
        answer = "AI инженер временно недоступен."

    return {"answer": answer}
