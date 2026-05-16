"""
Admin endpoints — управление сезонами.
POST /api/admin/seasons               — создать сезон
GET  /api/admin/seasons               — список сезонов
PUT  /api/admin/seasons/{id}/calendar — обновить календарь сезона
GET  /api/admin/tracks                — список всех трасс F1 25
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from backend.db.base import get_db
from backend.models.models import Season, User
from backend.services.auth_dependencies import get_current_user, require_system_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Трассы, которые реально присутствуют в F1 25 (без коротких и нереальных)
F1_25_TRACKS = [
    {"id": 0,  "name": "Melbourne",          "gp": "Australian GP"},
    {"id": 2,  "name": "Shanghai",           "gp": "Chinese GP"},
    {"id": 13, "name": "Suzuka",             "gp": "Japanese GP"},
    {"id": 3,  "name": "Sakhir (Bahrain)",   "gp": "Bahrain GP"},
    {"id": 29, "name": "Jeddah",             "gp": "Saudi Arabian GP"},
    {"id": 30, "name": "Miami",              "gp": "Miami GP"},
    {"id": 27, "name": "Imola",              "gp": "Emilia Romagna GP"},
    {"id": 5,  "name": "Monaco",             "gp": "Monaco GP"},
    {"id": 4,  "name": "Catalunya",          "gp": "Spanish GP"},
    {"id": 6,  "name": "Montreal",           "gp": "Canadian GP"},
    {"id": 17, "name": "Austria",            "gp": "Austrian GP"},
    {"id": 7,  "name": "Silverstone",        "gp": "British GP"},
    {"id": 10, "name": "Spa",                "gp": "Belgian GP"},
    {"id": 9,  "name": "Hungaroring",        "gp": "Hungarian GP"},
    {"id": 26, "name": "Zandvoort",          "gp": "Dutch GP"},
    {"id": 11, "name": "Monza",              "gp": "Italian GP"},
    {"id": 20, "name": "Baku (Azerbaijan)",  "gp": "Azerbaijan GP"},
    {"id": 12, "name": "Singapore",          "gp": "Singapore GP"},
    {"id": 15, "name": "Texas (COTA)",       "gp": "United States GP"},
    {"id": 19, "name": "Mexico",             "gp": "Mexico City GP"},
    {"id": 16, "name": "Brazil",             "gp": "São Paulo GP"},
    {"id": 31, "name": "Las Vegas",          "gp": "Las Vegas GP"},
    {"id": 32, "name": "Losail (Qatar)",     "gp": "Qatar GP"},
    {"id": 14, "name": "Abu Dhabi",          "gp": "Abu Dhabi GP"},
    # Дополнительные трассы, доступные в F1 25
    {"id": 28, "name": "Portimao",           "gp": "Portuguese GP"},
    {"id": 1,  "name": "Paul Ricard",        "gp": "French GP"},
    {"id": 8,  "name": "Hockenheim",         "gp": "German GP"},
]


class SeasonCreate(BaseModel):
    name:          str
    calendar:      list[dict] = []
    points_system: dict = {}


@router.post("/seasons")
async def create_season(req: SeasonCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    require_system_admin(user)
    season = Season(
        name=req.name,
        status="active",
        calendar=req.calendar,
        points_system=req.points_system,
    )
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return {
        "id":         season.id,
        "name":       season.name,
        "status":     season.status,
        "created_at": season.created_at.isoformat() if season.created_at else None,
    }


@router.get("/tracks")
async def list_tracks():
    """Список всех трасс F1 25 доступных для составления календаря."""
    return F1_25_TRACKS


@router.get("/seasons")
async def list_seasons(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Season).order_by(Season.id))
    seasons = res.scalars().all()
    return [
        {
            "id":         s.id,
            "name":       s.name,
            "status":     s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in seasons
    ]


class CalendarEntry(BaseModel):
    round:      int
    track_id:   int
    track_name: str


@router.put("/seasons/{season_id}/calendar")
async def update_season_calendar(
    season_id: int,
    entries: List[CalendarEntry],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Обновить (перезаписать) календарь сезона."""
    require_system_admin(user)
    season = await db.get(Season, season_id)
    if not season:
        raise HTTPException(404, "Season not found")

    season.calendar = [e.dict() for e in entries]
    await db.commit()
    return {"ok": True, "rounds": len(entries)}
