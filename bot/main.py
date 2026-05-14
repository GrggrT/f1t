"""Точка входа Telegram бота."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN
from bot.handlers import commands, achievements, stewards, contracts
from bot.callbacks import player_map
from bot.internal_server import start_internal_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN env var is not set")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(commands.router)
    dp.include_router(achievements.router)
    dp.include_router(stewards.router)
    dp.include_router(player_map.router)
    dp.include_router(contracts.router)

    # Запускаем внутренний HTTP сервер для уведомлений от backend
    await start_internal_server(bot, port=8001)

    log.info("Starting F1 League Bot...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
