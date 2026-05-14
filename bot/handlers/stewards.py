"""
/remove_penalty — команда для стюардов (только admin).
Использование:
  /remove_penalty @PlayerName 5s [причина]     → снять 5 секунд
  /remove_penalty @PlayerName +5s [причина]    → добавить 5 секунд
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import httpx
import re

from bot.config import API_URL, SEASON_ID, ADMIN_IDS

router = Router()


@router.message(Command("remove_penalty", "penalty"))
async def cmd_remove_penalty(msg: Message) -> None:
    if not msg.from_user or msg.from_user.id not in ADMIN_IDS:
        await msg.reply("⛔ Только стюарды могут изменять штрафы.")
        return

    # Парсим: /remove_penalty ИмяИгрока [-]5s [причина]
    text = msg.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply(
            "Использование:\n"
            "<code>/remove_penalty ИмяИгрока -5s [причина]</code>\n"
            "<code>/remove_penalty ИмяИгрока +5s [причина]</code>",
            parse_mode="HTML"
        )
        return

    args = parts[1]
    # Паттерн: имя секунды причина
    m = re.match(r"^(.+?)\s+([+-]?\d+)s?\s*(.*)$", args.strip())
    if not m:
        await msg.reply("Не могу распарсить. Пример: <code>Григорий -5s спорное касание</code>", parse_mode="HTML")
        return

    player_name  = m.group(1).strip()
    seconds      = int(m.group(2))
    reason       = m.group(3).strip() or "Решение стюардов"

    # Ищем последнюю гонку и player_id по имени
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Получаем список игроков
            pr = await client.get(f"{API_URL}/api/players")
            players = pr.json() if pr.status_code == 200 else []

            player = next(
                (p for p in players if p["name"].lower() == player_name.lower()),
                None
            )
            if not player:
                await msg.reply(f"Игрок <b>{player_name}</b> не найден.", parse_mode="HTML")
                return

            # Последняя гонка
            races_r = await client.get(f"{API_URL}/api/races/{SEASON_ID}")
            races   = races_r.json() if races_r.status_code == 200 else []
            if not races:
                await msg.reply("Нет гонок в сезоне.")
                return

            last_race = sorted(races, key=lambda r: r["round"])[-1]

            # Применяем коррекцию
            cr = await client.post(f"{API_URL}/api/stewards/penalty", json={
                "race_id":        last_race["id"],
                "player_id":      player["id"],
                "correction_sec": seconds,
                "reason":         reason,
                "applied_by":     player["id"],  # TODO: admin player_id
            })

            if cr.status_code == 200:
                data = cr.json()
                sign = "➖" if seconds < 0 else "➕"
                await msg.reply(
                    f"{sign} <b>{data['player']}</b>: {data['action']}\n"
                    f"Причина: <i>{reason}</i>\n"
                    f"Standings пересчитаны.",
                    parse_mode="HTML"
                )
            else:
                await msg.reply(f"Ошибка: {cr.text}")

    except Exception as e:
        await msg.reply(f"Ошибка: {e}")
