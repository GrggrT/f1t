"""Practice/personal telemetry sessions — data collected by launcher in personal mode."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.db.base import get_db
from backend.models.models import User
from backend.services.auth_dependencies import get_current_user

router = APIRouter(prefix="/api/practice", tags=["practice"])


class CreateSessionReq(BaseModel):
    track_id: int
    track_name: str = ""
    session_type: str = "practice"


class AddLapReq(BaseModel):
    lap_number: int
    lap_time_ms: float
    sector1_ms: float | None = None
    sector2_ms: float | None = None
    sector3_ms: float | None = None
    tyre_compound: str | None = None
    valid: bool = True


class AddLapsBatchReq(BaseModel):
    laps: list[AddLapReq]


@router.post("/sessions")
async def create_session(req: CreateSessionReq, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text(
        "INSERT INTO practice_sessions (user_id, track_id, track_name, session_type) "
        "VALUES (:uid, :tid, :tn, :st) RETURNING id, created_at"
    ), {"uid": user.id, "tid": req.track_id, "tn": req.track_name, "st": req.session_type})
    row = result.fetchone()
    await db.commit()
    return {"id": row[0], "created_at": str(row[1])}


@router.post("/sessions/{session_id}/laps")
async def add_laps(session_id: int, req: AddLapsBatchReq, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    check = await db.execute(text(
        "SELECT id FROM practice_sessions WHERE id = :sid AND user_id = :uid"
    ), {"sid": session_id, "uid": user.id})
    if not check.fetchone():
        raise HTTPException(404, "Session not found")

    for lap in req.laps:
        await db.execute(text(
            "INSERT INTO practice_laps (session_id, lap_number, lap_time_ms, sector1_ms, sector2_ms, sector3_ms, tyre_compound, valid) "
            "VALUES (:sid, :ln, :lt, :s1, :s2, :s3, :tc, :v)"
        ), {
            "sid": session_id, "ln": lap.lap_number, "lt": lap.lap_time_ms,
            "s1": lap.sector1_ms, "s2": lap.sector2_ms, "s3": lap.sector3_ms,
            "tc": lap.tyre_compound, "v": lap.valid,
        })

    await db.execute(text(
        "UPDATE practice_sessions SET total_laps = (SELECT COUNT(*) FROM practice_laps WHERE session_id = :sid), "
        "best_lap_ms = (SELECT MIN(lap_time_ms) FROM practice_laps WHERE session_id = :sid AND valid = true) "
        "WHERE id = :sid"
    ), {"sid": session_id})
    await db.commit()
    return {"ok": True, "laps_added": len(req.laps)}


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(text(
        "UPDATE practice_sessions SET ended_at = NOW() WHERE id = :sid AND user_id = :uid"
    ), {"sid": session_id, "uid": user.id})
    await db.commit()
    return {"ok": True}


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text(
        "SELECT id, track_id, track_name, session_type, total_laps, best_lap_ms, created_at, ended_at "
        "FROM practice_sessions WHERE user_id = :uid ORDER BY created_at DESC LIMIT 50"
    ), {"uid": user.id})
    rows = result.fetchall()
    return [
        {
            "id": r[0], "track_id": r[1], "track_name": r[2], "session_type": r[3],
            "total_laps": r[4], "best_lap_ms": r[5],
            "created_at": str(r[6]), "ended_at": str(r[7]) if r[7] else None,
        }
        for r in rows
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sess = await db.execute(text(
        "SELECT id, track_id, track_name, session_type, total_laps, best_lap_ms, created_at, ended_at "
        "FROM practice_sessions WHERE id = :sid AND user_id = :uid"
    ), {"sid": session_id, "uid": user.id})
    row = sess.fetchone()
    if not row:
        raise HTTPException(404, "Session not found")

    laps = await db.execute(text(
        "SELECT lap_number, lap_time_ms, sector1_ms, sector2_ms, sector3_ms, tyre_compound, valid "
        "FROM practice_laps WHERE session_id = :sid ORDER BY lap_number"
    ), {"sid": session_id})

    return {
        "id": row[0], "track_id": row[1], "track_name": row[2], "session_type": row[3],
        "total_laps": row[4], "best_lap_ms": row[5],
        "created_at": str(row[6]), "ended_at": str(row[7]) if row[7] else None,
        "laps": [
            {"lap_number": l[0], "lap_time_ms": l[1], "sector1_ms": l[2], "sector2_ms": l[3],
             "sector3_ms": l[4], "tyre_compound": l[5], "valid": l[6]}
            for l in laps.fetchall()
        ],
    }
