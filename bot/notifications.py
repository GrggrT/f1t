"""
Авто-публикация результатов в Telegram-группу.
Вызывается из backend (webhook или polling от FastAPI).
"""
import io
from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.formatters import fmt_race_results, fmt_wdc_standings, fmt_wcc_standings
from bot.card_generator import generate_race_card, generate_standings_card
from bot.config import CHAT_ID


async def post_race_results(bot: Bot, race: dict, wdc: list, wcc: list) -> None:
    """Постит: текст результатов + PNG карточка + WDC + WCC."""
    if not CHAT_ID:
        print("[BOT] CHAT_ID not set, skipping post")
        return

    # 1. Текст результатов
    text = fmt_race_results(race)
    await bot.send_message(CHAT_ID, text, parse_mode="HTML")

    # 2. PNG карточка
    try:
        card_bytes = generate_race_card(race)
        card_file  = BufferedInputFile(card_bytes, filename="race_result.png")
        await bot.send_photo(CHAT_ID, card_file)
    except Exception as e:
        print(f"[BOT] Card generation failed: {e}")

    # 3. WDC standings текстом
    if wdc:
        wdc_text = fmt_wdc_standings(wdc)
        await bot.send_message(CHAT_ID, wdc_text, parse_mode="HTML")

        # PNG карточка standings
        try:
            card_bytes = generate_standings_card(wdc, "DRIVERS CHAMPIONSHIP")
            card_file  = BufferedInputFile(card_bytes, filename="wdc.png")
            await bot.send_photo(CHAT_ID, card_file)
        except Exception as e:
            print(f"[BOT] WDC card generation failed: {e}")

    # 4. WCC standings
    if wcc:
        wcc_text = fmt_wcc_standings(wcc)
        await bot.send_message(CHAT_ID, wcc_text, parse_mode="HTML")


async def post_achievements(bot: Bot, unlocks: list[dict]) -> None:
    """Постит все новые достижения после гонки одним сообщением."""
    if not unlocks or not CHAT_ID:
        return
    lines = ["🏆 <b>Achievement Unlocked!</b>\n"]
    for u in unlocks:
        lines.append(f"{u['ach_icon']} <b>{u['ach_name']}</b> → <b>{u['player_name']}</b>")
        lines.append(f"   <i>{u['ach_desc']}</i>")
    await bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="HTML")


async def post_fun_stats(bot: Bot, stats: list[dict]) -> None:
    """Постит fun-stats каждые 4 гонки."""
    if not stats or not CHAT_ID:
        return
    lines = ["📊 <b>Fun Stats</b> — итоги последних 4 гонок\n"]
    for s in stats:
        lines.append(f"{s['icon']} <b>{s['title']}</b>: {s['player_name']} — {s['value']}")
    await bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="HTML")


async def ask_unknown_player(bot: Bot, steam_name: str, race_id: int, players: list[dict]) -> None:
    """Спрашивает кто такой неизвестный Steam-игрок."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(
            text=p["name"],
            callback_data=f"map_player:{steam_name}:{p['id']}:{race_id}"
        )]
        for p in players
    ]
    buttons.append([InlineKeyboardButton(text="❓ Новый игрок", callback_data=f"new_player:{steam_name}:{race_id}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(
        CHAT_ID,
        f"🔍 Кто такой <b>{steam_name}</b> в гонке?\nВыберите из списка или добавьте нового:",
        reply_markup=kb,
        parse_mode="HTML",
    )
