"""
POST /api/contracts/generate/{season_id}  — генерация предложений (конец сезона)
GET  /api/contracts/{season_id}           — все предложения
POST /api/contracts/accept                — принять контракт
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.db.base import get_db
from backend.models.models import WebUser
from backend.services.auth_dependencies import get_current_user
from backend.services.auth_helpers import require_season_moderator
from backend.services.contract_generator import generate_contracts, apply_contract

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

# Кэш предложений в памяти (достаточно для 5 человек)
_offers_cache: dict[int, list[dict]] = {}   # season_id → offers


@router.post("/generate/{season_id}")
async def generate(
    season_id: int,
    background_tasks: BackgroundTasks,
    _: object = Depends(require_season_moderator),
):
    """Запускает генерацию контрактов в фоне.

    Auth: only moderator+ of the lobby owning this season can fire generation,
    since it produces and broadcasts offers to all participants via the bot.
    """
    async def _run():
        offers = await generate_contracts(season_id)
        _offers_cache[season_id] = offers
        # Уведомляем бот
        import httpx, os
        bot_url = os.getenv("BOT_NOTIFY_URL", "").replace("/internal/race_uploaded", "/internal/contracts_ready")
        secret  = os.getenv("BOT_NOTIFY_SECRET", "")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(bot_url, json={"season_id": season_id, "offers": offers},
                                  headers={"X-Secret": secret})
        except Exception as e:
            print(f"[CONTRACTS] Notify failed: {e}")

    background_tasks.add_task(_run)
    return {"status": "generating", "message": "Contracts are being generated, check back in ~1 minute"}


@router.get("/{season_id}")
async def get_contracts(season_id: int):
    offers = _offers_cache.get(season_id)
    if not offers:
        # Попробуем сгенерировать синхронно (на случай перезапуска)
        offers = await generate_contracts(season_id)
        _offers_cache[season_id] = offers
    return offers


class AcceptRequest(BaseModel):
    player_id:     int
    team_id:       int
    new_season_id: int


@router.post("/accept")
async def accept_contract(
    req: AcceptRequest,
    user: WebUser = Depends(get_current_user),
):
    """Authenticated, ownership-checked: a user can only accept on behalf of
    the player profile linked to their WebUser. System admins bypass."""
    if not user.is_system_admin and user.player_id != req.player_id:
        raise HTTPException(403, "You can only accept contracts for your own player profile")
    result = await apply_contract(req.player_id, req.team_id, req.new_season_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Failed"))
    return result
