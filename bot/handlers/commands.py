"""Обработчики команд бота."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from bot import api_client
from bot.formatters import (
    fmt_wdc_standings, fmt_wcc_standings,
    fmt_player_stats, fmt_calendar, fmt_race_results,
)
from bot.card_generator import generate_standings_card
from bot.config import SEASON_ID

router = Router()


@router.message(Command("standings", "s"))
async def cmd_standings(msg: Message) -> None:
    wdc = await api_client.get_standings()
    if not wdc:
        await msg.reply("Нет данных 😔")
        return

    text = fmt_wdc_standings(wdc)
    await msg.reply(text, parse_mode="HTML")

    try:
        card = generate_standings_card(wdc, "DRIVERS CHAMPIONSHIP")
        await msg.answer_photo(BufferedInputFile(card, "wdc.png"))
    except Exception:
        pass


@router.message(Command("constructors", "cc"))
async def cmd_constructors(msg: Message) -> None:
    wcc = await api_client.get_constructors()
    if not wcc:
        await msg.reply("Нет данных 😔")
        return

    text = fmt_wcc_standings(wcc)
    await msg.reply(text, parse_mode="HTML")

    try:
        card = generate_standings_card(
            [{"driver_name": s["team_name"], "team_color": s["team_color"],
              "total_points": s["total_points"], "position": s["position"],
              "is_human": False} for s in wcc],
            "CONSTRUCTORS CHAMPIONSHIP"
        )
        await msg.answer_photo(BufferedInputFile(card, "wcc.png"))
    except Exception:
        pass


@router.message(Command("last", "l"))
async def cmd_last(msg: Message) -> None:
    race = await api_client.get_last_race()
    if not race:
        await msg.reply("Ещё не было гонок 🏎")
        return

    text = fmt_race_results(race)
    await msg.reply(text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(msg: Message) -> None:
    """
    /stats — своя статистика по telegram_id.
    /stats 5 — статистика игрока по player_id.
    """
    args = msg.text.split()[1:] if msg.text else []
    tg_id = msg.from_user.id if msg.from_user else None

    if not args:
        # Ищем по telegram_id
        if not tg_id:
            await msg.reply("Не удалось определить Telegram ID")
            return

        import httpx
        from bot.config import API_URL
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{API_URL}/api/players/by_telegram/{tg_id}")
                if r.status_code == 404:
                    await msg.reply(
                        "Ты ещё не зарегистрирован.\n"
                        "Напиши /register чтобы создать профиль.",
                        parse_mode="HTML"
                    )
                    return
                player = r.json()
                player_id = player["id"]
        except Exception as e:
            await msg.reply(f"Ошибка: {e}")
            return
    else:
        try:
            player_id = int(args[0])
        except ValueError:
            await msg.reply("Использование: /stats [player_id]")
            return

    stats = await api_client.get_player_stats(player_id)
    if not stats:
        await msg.reply("Игрок не найден 😔")
        return

    await msg.reply(fmt_player_stats(stats), parse_mode="HTML")


@router.message(Command("calendar", "cal"))
async def cmd_calendar(msg: Message) -> None:
    cal = await api_client.get_calendar()
    if not cal:
        await msg.reply("Календарь пуст 😔")
        return
    await msg.reply(fmt_calendar(cal), parse_mode="HTML")


@router.message(Command("register"))
async def cmd_register(msg: Message) -> None:
    """Регистрация — имя берётся из Telegram профиля."""
    tg_id = msg.from_user.id if msg.from_user else None

    # Определяем имя: из аргументов или из Telegram профиля
    args = msg.text.split()[1:] if msg.text else []
    if args:
        name = " ".join(args)
    else:
        user = msg.from_user
        name = (user.full_name or user.first_name or "Player") if user else "Player"

    import httpx
    from bot.config import API_URL
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_URL}/api/players/register", json={
                "telegram_id": tg_id,
                "name": name,
            })
            if r.status_code == 200:
                data = r.json()
                if data.get("already_exists"):
                    await msg.reply(
                        f"Ты уже зарегистрирован как <b>{data['name']}</b> (ID: {data['id']}) ✅\n\n"
                        f"Добавь Steam ник из F1 25: /addsteam Твой_Ник\n"
                        f"Статистика: /stats",
                        parse_mode="HTML"
                    )
                else:
                    await msg.reply(
                        f"✅ Добро пожаловать, <b>{data['name']}</b>! (ID: {data['id']})\n\n"
                        f"Теперь добавь ник из F1 25 — именно так тебя видит игра:\n"
                        f"/addsteam Твой_Ник_В_Игре",
                        parse_mode="HTML"
                    )
            else:
                await msg.reply(f"Ошибка регистрации: {r.text}")
    except Exception as e:
        await msg.reply(f"Ошибка: {e}")


@router.message(Command("addsteam"))
async def cmd_addsteam(msg: Message) -> None:
    """
    Привязать Steam к профилю.
    Принимает: ссылку на профиль, SteamID64 или ник в игре.
    """
    args = msg.text.split()[1:] if msg.text else []
    if not args:
        await msg.reply(
            "Укажи ссылку на Steam профиль или ник из F1 25:\n\n"
            "<b>Рекомендуется (по Steam ID):</b>\n"
            "/addsteam https://steamcommunity.com/id/ТвойВанити\n\n"
            "<b>Или просто ник из игры:</b>\n"
            "/addsteam ТвойНикВF1_25\n\n"
            "💡 Со Steam ссылкой привязка останется даже если сменишь имя.",
            parse_mode="HTML"
        )
        return

    steam_input = " ".join(args)
    tg_id = msg.from_user.id if msg.from_user else None

    await msg.reply("🔍 Проверяю...", parse_mode="HTML")

    import httpx
    from bot.config import API_URL
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{API_URL}/api/players/add_steam", json={
                "telegram_id": tg_id,
                "steam_input": steam_input,
            })
            if r.status_code == 200:
                data = r.json()
                if data.get("resolved"):
                    await msg.reply(
                        f"✅ Steam профиль привязан!\n\n"
                        f"👤 Steam ник: <b>{data['persona_name']}</b>\n"
                        f"🔗 Профиль: {data.get('steam_url', '')}\n\n"
                        f"При смене ника в Steam — привязка сохранится автоматически.",
                        parse_mode="HTML"
                    )
                else:
                    names = data.get("steam_names", [])
                    await msg.reply(
                        f"✅ Ник <b>{steam_input}</b> добавлен.\n\n"
                        f"💡 Совет: укажи ссылку на Steam профиль чтобы привязка "
                        f"не слетела при смене ника:\n"
                        f"/addsteam https://steamcommunity.com/id/ТвойПрофиль",
                        parse_mode="HTML"
                    )
            elif r.status_code == 404:
                await msg.reply("Сначала зарегистрируйся: /register")
            else:
                data = r.json()
                await msg.reply(f"❌ {data.get('detail', r.text)}")
    except Exception as e:
        await msg.reply(f"Ошибка: {e}")


@router.message(Command("help", "start"))
async def cmd_help(msg: Message) -> None:
    text = (
        "🏎 <b>F1 League Bot</b>\n\n"
        "/standings — таблица пилотов\n"
        "/constructors — таблица команд\n"
        "/last — последняя гонка\n"
        "/stats [id] — статистика игрока\n"
        "/calendar — расписание сезона\n"
        "/register — зарегистрироваться (имя из Telegram)\n"
        "/addsteam [ссылка или ник] — привязать Steam профиль\n"
        "/contracts — контрактные предложения (конец сезона)\n"
        "/accept Команда — принять контракт\n"
    )
    await msg.reply(text, parse_mode="HTML")
