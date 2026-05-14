"""
Стюарды — отмена/добавление штрафных секунд после гонки.
POST /api/stewards/penalty — применить коррекцию
GET  /api/stewards/corrections/{race_id} — история коррекций
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.db.base import get_db
from backend.models.models import Race, RaceResult, PenaltyCorrection, Player, WebUser
from backend.services.auth_dependencies import get_current_user, require_system_admin
from backend.services.standings_service import recalc_standings

router = APIRouter(prefix="/api/stewards", tags=["stewards"])


class PenaltyRequest(BaseModel):
    race_id:        int
    player_id:      int
    correction_sec: int      # отрицательное = снять штраф, положительное = добавить
    reason:         str


@router.post("/penalty")
async def apply_penalty_correction(req: PenaltyRequest, db: AsyncSession = Depends(get_db), user: WebUser = Depends(get_current_user)):
    require_system_admin(user)
    # Проверяем гонку
    race_res = await db.execute(select(Race).where(Race.id == req.race_id))
    race = race_res.scalars().first()
    if not race:
        raise HTTPException(404, "Race not found")

    # Находим результат игрока
    rr_res = await db.execute(
        select(RaceResult).where(
            RaceResult.race_id  == req.race_id,
            RaceResult.player_id == req.player_id,
        )
    )
    rr = rr_res.scalars().first()
    if not rr:
        raise HTTPException(404, "Player result not found in this race")

    # Применяем коррекцию к total_race_time
    if rr.total_race_time is not None:
        rr.total_race_time += req.correction_sec

    # Логируем
    db.add(PenaltyCorrection(
        race_id=req.race_id,
        player_id=req.player_id,
        correction_sec=req.correction_sec,
        reason=req.reason,
        applied_by=user.player_id,
    ))

    await db.commit()

    # Пересчитываем позиции в этой гонке на основе новых total_race_time
    await _recalc_positions(db, req.race_id)

    # Пересчитываем standings
    await recalc_standings(race.season_id)

    player_res = await db.execute(select(Player).where(Player.id == req.player_id))
    player = player_res.scalars().first()

    action = "снято" if req.correction_sec < 0 else "добавлено"
    return {
        "ok":      True,
        "player":  player.name if player else str(req.player_id),
        "action":  f"{abs(req.correction_sec)}s {action}",
        "reason":  req.reason,
    }


async def _recalc_positions(db: AsyncSession, race_id: int) -> None:
    """Пересчитывает позиции финишировавших пилотов по total_race_time."""
    rr_res = await db.execute(
        select(RaceResult).where(RaceResult.race_id == race_id)
    )
    all_results = rr_res.scalars().all()

    finished   = [r for r in all_results if r.result_status == 3 and r.total_race_time]
    not_finish = [r for r in all_results if r not in finished]

    # Сортируем финишировавших по total_race_time
    finished.sort(key=lambda r: r.total_race_time)

    for i, r in enumerate(finished):
        r.position = i + 1

    # Не финишировавшие идут после
    for i, r in enumerate(not_finish):
        r.position = len(finished) + i + 1

    # Пересчитываем очки
    from shared.points_system import calc_points
    for r in all_results:
        r.points = calc_points(r.position or 99, r.has_fastest_lap, r.result_status)

    await db.commit()


@router.get("/corrections/{race_id}")
async def get_corrections(race_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(PenaltyCorrection, Player.name.label("player_name"))
        .join(Player, Player.id == PenaltyCorrection.player_id)
        .where(PenaltyCorrection.race_id == race_id)
        .order_by(PenaltyCorrection.applied_at.desc())
    )
    rows = res.all()
    return [
        {
            "id":             pc.id,
            "player_name":    pname,
            "correction_sec": pc.correction_sec,
            "reason":         pc.reason,
            "applied_at":     pc.applied_at,
        }
        for pc, pname in rows
    ]
