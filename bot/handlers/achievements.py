"""Команды бота для просмотра достижений."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import httpx
from bot.config import API_URL, SEASON_ID

router = Router()


@router.message(Command("achievements", "ach"))
async def cmd_achievements(msg: Message) -> None:
    """Показывает все достижения и кто их получил."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_URL}/api/achievements/{SEASON_ID}")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        await msg.reply(f"Ошибка: {e}")
        return

    if not data:
        await msg.reply("Ещё никто не получил достижений 😔")
        return

    lines = ["🏆 <b>Достижения сезона</b>\n"]
    for entry in data:
        icon   = entry.get("icon", "🏅")
        name   = entry.get("ach_name", "?")
        player = entry.get("player_name", "?")
        lines.append(f"{icon} <b>{name}</b> → {player}")

    await msg.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("records"))
async def cmd_records(msg: Message) -> None:
    """Рекорды трасс — абсолютный fastest lap."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_URL}/api/records/{SEASON_ID}")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        await msg.reply(f"Ошибка: {e}")
        return

    if not data:
        await msg.reply("Нет записей 😔")
        return

    lines = ["⚡ <b>Рекорды трасс</b>\n"]
    for rec in data:
        ms    = rec.get("best_lap_ms")
        m     = ms // 60000 if ms else 0
        s     = ((ms % 60000) / 1000) if ms else 0
        tstr  = f"{m}:{s:06.3f}" if m else f"{s:.3f}s"
        lines.append(
            f"🏁 <b>{rec['track_name']}</b>\n"
            f"   {tstr} — {rec['driver_name']} ({rec.get('player_name','AI')})"
        )

    await msg.reply("\n".join(lines), parse_mode="HTML")
