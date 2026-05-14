"""
Маленький HTTP сервер внутри бота для приёма уведомлений от backend.
Запускается в том же процессе что и бот (aiohttp).
"""
import os
from aiohttp import web
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from bot import api_client
from bot.notifications import post_race_results, ask_unknown_player, post_achievements, post_fun_stats
from bot.config import BOT_NOTIFY_SECRET

_bot_instance: Bot | None = None


def set_bot(bot: Bot) -> None:
    global _bot_instance
    _bot_instance = bot


async def handle_race_uploaded(request: web.Request) -> web.Response:
    secret = request.headers.get("X-Secret", "")
    if secret != BOT_NOTIFY_SECRET:
        return web.Response(status=403)

    data = await request.json()
    race_id   = data.get("race_id")
    season_id = data.get("season_id")

    if not race_id or not _bot_instance:
        return web.Response(status=400)

    # Подтягиваем данные и постим
    race = await api_client.get_race(race_id)
    wdc  = await api_client.get_standings()
    wcc  = await api_client.get_constructors()

    if race:
        await post_race_results(_bot_instance, race, wdc, wcc)

        # Достижения
        unlocks = data.get("achievements", [])
        if unlocks:
            await post_achievements(_bot_instance, unlocks)

        # Fun stats (каждые 4 гонки)
        fun_stats = data.get("fun_stats")
        if fun_stats:
            await post_fun_stats(_bot_instance, fun_stats)

        # Если есть неразмапленные игроки — спрашиваем
        unresolved_names = data.get("unresolved_players", [])
        if unresolved_names:
            players_list = await api_client.get("/api/players") or []
            for steam_name in unresolved_names:
                await ask_unknown_player(_bot_instance, steam_name, race_id, players_list)

    return web.Response(text="ok")


async def handle_debrief(request: web.Request) -> web.Response:
    """Личное сообщение с AI-дебрифом конкретному игроку."""
    secret = request.headers.get("X-Secret", "")
    if secret != BOT_NOTIFY_SECRET:
        return web.Response(status=403)

    if not _bot_instance:
        return web.Response(status=503)

    data        = await request.json()
    telegram_id = data.get("telegram_id")
    track_name  = data.get("track_name", "Unknown")
    debrief     = data.get("debrief", "")

    if not telegram_id or not debrief:
        return web.Response(status=400)

    text = (
        f"🏎 <b>AI Race Engineer — {track_name}</b>\n\n"
        f"{debrief}"
    )
    try:
        await _bot_instance.send_message(telegram_id, text)
    except TelegramForbiddenError:
        print(f"[BOT] Player {telegram_id} blocked the bot — skipping debrief")
    except Exception as e:
        print(f"[BOT] Failed to send debrief to {telegram_id}: {e}")

    return web.Response(text="ok")


async def handle_contracts_ready(request: web.Request) -> web.Response:
    """Контракты сгенерированы — уведомляем игроков в личку."""
    secret = request.headers.get("X-Secret", "")
    if secret != BOT_NOTIFY_SECRET:
        return web.Response(status=403)

    if not _bot_instance:
        return web.Response(status=503)

    data      = await request.json()
    season_id = data.get("season_id")
    offers    = data.get("offers", [])   # список [{player_id, player_name, ...}]

    if not season_id or not offers:
        return web.Response(status=400)

    # Подтягиваем telegram_id для каждого игрока
    players_list = await api_client.get("/api/players") or []
    player_tg: dict[int, int] = {
        p["id"]: p["telegram_id"]
        for p in players_list
        if p.get("telegram_id")
    }

    for player_offer in offers:
        pid = player_offer.get("player_id")
        tg  = player_tg.get(pid)
        if not tg:
            continue

        lines = [
            f"📋 <b>Контрактные предложения — Сезон {season_id + 1}</b>\n",
            f"Привет, <b>{player_offer['player_name']}</b>! "
            f"Твой рейтинг: <b>{player_offer['rating']:.0f}/100</b> "
            f"(команда: {player_offer['current_team']})\n",
        ]
        for offer in player_offer.get("offers", []):
            tier_icon = {"HOT OFFER": "🔥", "OFFER": "📄", "LONG-SHOT": "🎲"}.get(offer["tier"], "📄")
            lines.append(
                f"{tier_icon} <b>{offer['tier']}</b> — {offer['team_name']}\n"
                f"<i>{offer.get('narrative', '')}</i>\n"
            )
        lines.append("\nДля принятия предложения: /accept [название команды]")

        try:
            await _bot_instance.send_message(tg, "\n".join(lines))
        except TelegramForbiddenError:
            print(f"[BOT] Player {tg} blocked the bot")
        except Exception as e:
            print(f"[BOT] Failed to send contracts to {tg}: {e}")

    return web.Response(text="ok")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/internal/race_uploaded",   handle_race_uploaded)
    app.router.add_post("/internal/debrief",         handle_debrief)
    app.router.add_post("/internal/contracts_ready", handle_contracts_ready)
    return app


async def start_internal_server(bot: Bot, port: int = 8001) -> None:
    set_bot(bot)
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[BOT] Internal server started on :{port}")
