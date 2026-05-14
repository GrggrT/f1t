"""
Вызывает Telegram бот для авто-поста после каждой гонки.
Backend → HTTP → Bot API (aiogram).
Используется как BackgroundTask из /api/race/submit.
"""
import httpx
import os

def _bot_notify_url() -> str:
    return os.getenv("BOT_NOTIFY_URL", "http://bot:8001/internal/race_uploaded")


def _bot_notify_secret() -> str:
    return os.getenv("BOT_NOTIFY_SECRET", "internal-secret")


def _notify_delay_sec() -> float:
    try:
        return float(os.getenv("BOT_NOTIFY_DELAY_SEC", "3"))
    except (TypeError, ValueError):
        return 3.0


async def notify_race_uploaded(
    race_id: int,
    season_id: int,
    unresolved_players: list[str] | None = None,
) -> None:
    """Сообщает боту что новая гонка загружена — он сам подтянет данные и запостит."""
    import asyncio

    # Ждём чтобы standings и achievements успели посчитаться
    await asyncio.sleep(max(0.0, _notify_delay_sec()))

    # Собираем ачивки и fun_stats для передачи боту
    achievements = []
    fun_stats    = None

    try:
        from backend.services.achievement_engine import check_achievements_after_race
        from backend.services.fun_stats import compute_fun_stats
        achievements = await check_achievements_after_race(race_id, season_id)
        fun_stats    = await compute_fun_stats(season_id)
    except Exception as e:
        print(f"[NOTIFIER] achievements/fun_stats error: {e}")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                _bot_notify_url(),
                json={
                    "race_id":            race_id,
                    "season_id":          season_id,
                    "unresolved_players": unresolved_players or [],
                    "achievements":       achievements,
                    "fun_stats":          fun_stats,
                },
                headers={"X-Secret": _bot_notify_secret()},
            )
    except Exception as e:
        print(f"[NOTIFIER] Failed to notify bot: {e}")

    # AI Race Engineer дебрифы (в фоне, не блокируем)
    try:
        from backend.services.ai_engineer import run_debriefs_after_race
        await run_debriefs_after_race(race_id, season_id)
    except Exception as e:
        print(f"[NOTIFIER] AI debriefs error: {e}")
