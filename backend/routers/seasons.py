"""
Public seasons endpoint.
GET  /api/seasons           — список всех сезонов с базовой статистикой
GET  /api/seasons/{id}      — один сезон с деталями
POST /api/seasons/assistant — персональный AI-ассистент (анализ перформанса)
"""
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.base import get_db
from backend.models.models import Season, Race, RaceResult, ChampionshipStanding, User
from backend.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api/seasons", tags=["seasons"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"


@router.get("")
async def list_seasons(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Season).order_by(Season.id.desc())
    )
    seasons = res.scalars().all()

    out = []
    for s in seasons:
        # Количество гонок в сезоне
        race_cnt = await db.execute(
            select(func.count()).select_from(Race).where(Race.season_id == s.id)
        )
        races_played = race_cnt.scalar() or 0

        total_rounds = len(s.calendar) if isinstance(s.calendar, list) else 0

        out.append({
            "id":           s.id,
            "name":         s.name,
            "status":       s.status,
            "lobby_id":     s.lobby_id,
            "races_played": races_played,
            "total_rounds": total_rounds,
            "created_at":   s.created_at.isoformat() if s.created_at else None,
        })
    return out


@router.get("/{season_id}")
async def get_season(season_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(Season, season_id)
    if not s:
        raise HTTPException(404, "Season not found")

    race_cnt = await db.execute(
        select(func.count()).select_from(Race).where(Race.season_id == season_id)
    )
    races_played = race_cnt.scalar() or 0
    total_rounds = len(s.calendar) if isinstance(s.calendar, list) else 0

    return {
        "id":           s.id,
        "name":         s.name,
        "status":       s.status,
        "lobby_id":     s.lobby_id,
        "races_played": races_played,
        "total_rounds": total_rounds,
        "calendar":     s.calendar,
        "created_at":   s.created_at.isoformat() if s.created_at else None,
    }


class AssistantRequest(BaseModel):
    question: str
    # Sprint 3 / PR 3.1: `player_id` is gone — assistant operates on the
    # authenticated user only. Admin "ask about user X" is out of scope.


@router.post("/assistant")
async def personal_assistant(
    req: AssistantRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Персональный AI-ассистент — анализирует перформанс текущего пользователя."""
    user_row = user
    target_id = user.id

    standings_res = await db.execute(
        select(ChampionshipStanding, Season.name.label("season_name"))
        .join(Season, ChampionshipStanding.season_id == Season.id)
        .where(ChampionshipStanding.user_id == target_id)
        .order_by(Season.id)
    )
    standings_rows = standings_res.all()

    results_res = await db.execute(
        select(RaceResult, Race.track_name, Race.season_id)
        .join(Race, RaceResult.race_id == Race.id)
        .where(RaceResult.user_id == target_id)
        .order_by(Race.raced_at)
    )
    results_rows = results_res.all()

    # Агрегируем
    total_races  = len(results_rows)
    total_wins   = sum(1 for r, _, _ in results_rows if r.position == 1)
    total_podiums = sum(1 for r, _, _ in results_rows if r.position and r.position <= 3)
    total_dnfs   = sum(1 for r, _, _ in results_rows if r.result_status not in ("Finished", "finished"))
    total_pts    = sum(r.points for r, _, _ in results_rows)
    avg_pos      = (
        sum(r.position for r, _, _ in results_rows if r.position)
        / max(1, sum(1 for r, _, _ in results_rows if r.position))
    )

    seasons_summary = []
    for standing, sname in standings_rows:
        seasons_summary.append(
            f"Сезон «{sname}»: P{standing.position}, {standing.total_points} очков, "
            f"{standing.wins} побед, {standing.podiums} подиумов"
        )

    context = (
        f"Пилот: {user_row.name}\n"
        f"Всего гонок: {total_races}\n"
        f"Победы: {total_wins}, Подиумы: {total_podiums}, DNF: {total_dnfs}\n"
        f"Всего очков: {total_pts:.0f}\n"
        f"Средняя позиция: {avg_pos:.1f}\n"
        + ("\n".join(seasons_summary) if seasons_summary else "Нет данных по сезонам")
    )

    if not GROQ_API_KEY:
        return {"answer": "AI-ассистент недоступен: не задан GROQ_API_KEY."}

    import httpx
    system_prompt = (
        "Ты персональный F1 гоночный инженер. Отвечай кратко и конкретно по-русски. "
        "Используй данные пилота для анализа. Будь дружелюбным, но честным."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model":    GROQ_MODEL,
                    "messages": [
                        {"role": "system",    "content": system_prompt},
                        {"role": "user",      "content": f"Данные пилота:\n{context}\n\nВопрос: {req.question}"},
                    ],
                    "max_tokens":  400,
                    "temperature": 0.7,
                },
            )
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ASSISTANT] Error: {e}")
        answer = "AI-ассистент временно недоступен."

    return {"answer": answer}
