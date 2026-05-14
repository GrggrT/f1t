"""
/contracts  — посмотреть текущие предложения
/accept     — принять предложение команды
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot import api_client
from bot.config import SEASON_ID

router = Router()


@router.message(Command("contracts"))
async def cmd_contracts(message: Message) -> None:
    """Показывает текущие контрактные предложения для игрока."""
    # Определяем player_id по telegram_id
    players = await api_client.get("/api/players") or []
    me = next((p for p in players if p.get("telegram_id") == message.from_user.id), None)

    if not me:
        await message.answer("❌ Ты не зарегистрирован. Используй /register.")
        return

    all_offers = await api_client.get(f"/api/contracts/{SEASON_ID}")
    if not all_offers:
        await message.answer("📋 Контрактные предложения пока не сгенерированы.")
        return

    my_offers = next((o for o in all_offers if o["player_id"] == me["id"]), None)
    if not my_offers:
        await message.answer("📋 Для тебя нет предложений в этом сезоне.")
        return

    lines = [
        f"📋 <b>Контрактные предложения</b>\n",
        f"Рейтинг: <b>{my_offers['rating']:.0f}/100</b> | Команда: {my_offers['current_team']}\n",
    ]
    for offer in my_offers.get("offers", []):
        tier_icon = {"HOT OFFER": "🔥", "OFFER": "📄", "LONG-SHOT": "🎲"}.get(offer["tier"], "📄")
        lines.append(
            f"{tier_icon} <b>{offer['tier']}</b> — {offer['team_name']}\n"
            f"<i>{offer.get('narrative', '')}</i>\n"
        )

    lines.append("\nПринять предложение: /accept [название команды]")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("accept"))
async def cmd_accept(message: Message) -> None:
    """Принять контрактное предложение. Использование: /accept McLaren"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /accept [название команды]\nПример: /accept McLaren")
        return

    team_query = args[1].strip().lower()

    # Находим игрока
    players = await api_client.get("/api/players") or []
    me = next((p for p in players if p.get("telegram_id") == message.from_user.id), None)
    if not me:
        await message.answer("❌ Ты не зарегистрирован. Используй /register.")
        return

    # Находим предложения
    all_offers = await api_client.get(f"/api/contracts/{SEASON_ID}")
    if not all_offers:
        await message.answer("📋 Контрактные предложения пока не сгенерированы.")
        return

    my_offers = next((o for o in all_offers if o["player_id"] == me["id"]), None)
    if not my_offers:
        await message.answer("📋 Для тебя нет предложений.")
        return

    # Ищем команду по частичному совпадению
    matched_offer = None
    for offer in my_offers.get("offers", []):
        if team_query in offer["team_name"].lower():
            matched_offer = offer
            break

    if not matched_offer:
        teams_list = ", ".join(o["team_name"] for o in my_offers.get("offers", []))
        await message.answer(
            f"❌ Команда не найдена среди предложений.\n"
            f"Доступные: {teams_list}"
        )
        return

    new_season_id = SEASON_ID + 1
    result = await api_client.post("/api/contracts/accept", {
        "player_id":     me["id"],
        "team_id":       matched_offer["team_id"],
        "new_season_id": new_season_id,
    })

    if not result or not result.get("ok"):
        error = result.get("error", "Неизвестная ошибка") if result else "Сервер недоступен"
        await message.answer(f"❌ Ошибка: {error}")
        return

    team_color_map = {
        "Red Bull":    "🔵",
        "Ferrari":     "🔴",
        "Mercedes":    "⚪",
        "McLaren":     "🟠",
        "Aston Martin": "🟢",
        "Alpine":      "🔵",
        "Williams":    "🔵",
        "RB":          "🔵",
        "Haas":        "⚪",
        "Sauber":      "🟢",
    }
    icon = team_color_map.get(result["team_name"], "🏎")

    await message.answer(
        f"✅ Контракт подписан!\n\n"
        f"{icon} <b>{result['team_name']}</b>\n"
        f"Пилот: <b>{result['driver_name']}</b>\n\n"
        f"Увидимся в Сезоне {new_season_id}! 🏁"
    )
