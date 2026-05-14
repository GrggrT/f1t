"""Callback handlers для маппинга неизвестных Steam имён."""
import httpx
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.config import API_URL

router = Router()


@router.callback_query(F.data.startswith("map_player:"))
async def cb_map_player(call: CallbackQuery) -> None:
    """map_player:{steam_name}:{player_id}:{race_id}"""
    _, steam_name, player_id_str, race_id_str = call.data.split(":", 3)
    player_id = int(player_id_str)
    race_id   = int(race_id_str)

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/api/players/map_steam", json={
            "player_id":  player_id,
            "steam_name": steam_name,
            "race_id":    race_id,
        })

    if r.status_code == 200:
        data = r.json()
        await call.message.edit_text(
            f"✅ <b>{steam_name}</b> → <b>{data.get('player_name')}</b>\n"
            f"Имя добавлено в историю. Standings пересчитаны.",
            parse_mode="HTML"
        )
    else:
        await call.answer(f"Ошибка: {r.text}", show_alert=True)

    await call.answer()


@router.callback_query(F.data.startswith("new_player:"))
async def cb_new_player(call: CallbackQuery) -> None:
    """new_player:{steam_name}:{race_id}"""
    _, steam_name, race_id_str = call.data.split(":", 2)

    await call.message.edit_text(
        f"Создай профиль командой:\n"
        f"<code>/register ИмяИгрока</code>\n\n"
        f"Потом добавь Steam имя:\n"
        f"<code>/addsteam {steam_name}</code>",
        parse_mode="HTML"
    )
    await call.answer()
