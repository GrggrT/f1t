"""
Определения всех достижений.
Вызывается один раз при старте для сидирования таблицы achievements.
"""

ACHIEVEMENTS = [
    # =========================================================================
    # ГОНОЧНЫЕ (Race-based)
    # =========================================================================
    {"code": "ROCKET_START",     "name": "Rocket Start",     "description": "Поднялся на 3+ позиции в первом круге", "icon": "🚀"},
    {"code": "DOMINATOR",        "name": "Dominator",        "description": "3 победы подряд", "icon": "👑"},
    {"code": "RAIN_MASTER",      "name": "Rain Master",      "description": "Победа в дождевой гонке", "icon": "🌧"},
    {"code": "WRECKING_BALL",    "name": "Wrecking Ball",    "description": "3+ штрафа за одну гонку", "icon": "💥"},
    {"code": "SPEED_DEMON",      "name": "Speed Demon",      "description": "Абсолютный рекорд сезона по fastest lap", "icon": "⚡"},
    {"code": "PHOTO_FINISH",     "name": "Photo Finish",     "description": "Финишировал менее чем в 0.5с от соперника-игрока", "icon": "📸"},
    {"code": "LAST_TO_FIRST",    "name": "Last to First",    "description": "Победа стартовав с последнего места", "icon": "🔄"},
    {"code": "CLEAN_SWEEP",      "name": "Clean Sweep",      "description": "Pole + Fastest Lap + Победа", "icon": "🧹"},
    {"code": "CONSISTENCY_KING", "name": "Consistency King",  "description": "5 гонок подряд в топ-3", "icon": "🎯"},
    {"code": "GIANT_KILLER",     "name": "Giant Killer",      "description": "Финишировал выше лидера WDC", "icon": "🗡"},
    {"code": "PIT_MASTER",       "name": "Pit Master",        "description": "Поднялся на позицию после пит-стопа", "icon": "🔧"},
    {"code": "SURVIVOR",         "name": "Survivor",          "description": "Финишировал когда 2+ игроков DNF", "icon": "🛡"},
    {"code": "FIRST_BLOOD",      "name": "First Blood",       "description": "Первая победа в карьере", "icon": "🏆"},
    {"code": "CENTURION",        "name": "Centurion",         "description": "100+ очков за сезон", "icon": "💯"},
    {"code": "COMEBACK_KID",     "name": "Comeback Kid",      "description": "Подиум стартовав с P10+", "icon": "🔥"},
    {"code": "THE_WALL",         "name": "The Wall",          "description": "Весь сезон без штрафов (мин. 5 гонок)", "icon": "🧱"},
    {"code": "WEEKEND_WARRIOR",  "name": "Weekend Warrior",   "description": "3+ гонки за один день", "icon": "⚔️"},
    {"code": "HEARTBREAKER",     "name": "Heartbreaker",      "description": "DNF стартовав с топ-5", "icon": "💔"},
    {"code": "BOT_SLAYER",       "name": "Bot Slayer",        "description": "Финишировал выше Verstappen AI 5+ раз", "icon": "🤖"},
    {"code": "TEAMPLAYER",       "name": "Team Player",       "description": "Команда в топ-3 WCC", "icon": "🤝"},
    {"code": "CHAMPION",         "name": "Champion",          "description": "Выиграл WDC чемпионат", "icon": "🏅"},
    {"code": "OVERTAKE_KING",    "name": "Overtake King",     "description": "Больше всех обгонов за сезон", "icon": "💨"},

    # =========================================================================
    # НОВЫЕ ГОНОЧНЫЕ
    # =========================================================================
    {"code": "GRAND_CHELEM",     "name": "Grand Chelem",      "description": "Поул + лидерство каждый круг + FL + победа", "icon": "🏅"},
    {"code": "UNDERDOG",         "name": "Underdog",           "description": "Победа стартовав с P15+", "icon": "🐕"},
    {"code": "SAFETY_CAR_KING",  "name": "Safety Car King",    "description": "Выиграл 3+ позиции после Safety Car", "icon": "🟡"},
    {"code": "RAIN_DANCE",       "name": "Rain Dance",         "description": "Подиум в 3+ мокрых гонках за сезон", "icon": "🌊"},
    {"code": "LIGHTS_OUT",       "name": "Lights Out",         "description": "Лучший старт сезона: наибольший прирост позиций в 1 круге", "icon": "💡"},
    {"code": "LATE_BRAKER",      "name": "Late Braker",        "description": "Обгон за подиум на последних 3 кругах", "icon": "⏱"},
    {"code": "DOUBLE_POINTS",    "name": "Double Points",      "description": "2 подиума за один игровой вечер", "icon": "🎰"},
    {"code": "MARATHON_MAN",     "name": "Marathon Man",        "description": "4+ гонки подряд в очках (P1-P10)", "icon": "🏃"},
    {"code": "PENALTY_FREE",     "name": "Penalty Free",        "description": "10 гонок подряд без штрафов", "icon": "🕊"},
    {"code": "TEAM_ORDERS",      "name": "Team Orders",         "description": "Оба пилота команды на подиуме в одной гонке", "icon": "📋"},
    {"code": "THE_STIG",         "name": "The Stig",            "description": "Выиграл гонку с отрывом 10+ секунд", "icon": "🏁"},
    {"code": "BULLDOZER",        "name": "Bulldozer",           "description": "Обогнал всех людей в одной гонке (P1 среди humans)", "icon": "🚜"},

    # =========================================================================
    # ПРОГРЕССИЯ
    # =========================================================================
    {"code": "RISING_STAR",      "name": "Rising Star",         "description": "5 гонок подряд с улучшением позиции", "icon": "⭐"},
    {"code": "HOT_STREAK",       "name": "Hot Streak",          "description": "3 победы за один вечер", "icon": "🔥"},
    {"code": "FIFTY_RACES",      "name": "50 Races",            "description": "50 гонок в карьере", "icon": "5️⃣"},
    {"code": "HUNDRED_RACES",    "name": "100 Races",           "description": "100 гонок в карьере", "icon": "💯"},
    {"code": "POINTS_MACHINE",   "name": "Points Machine",      "description": "10 гонок подряд в очках", "icon": "⚙️"},
    {"code": "TWO_HUNDRED_PTS",  "name": "200 Points",          "description": "200+ очков за сезон", "icon": "💎"},
    {"code": "VETERAN",          "name": "Veteran",              "description": "3+ сезона в системе", "icon": "🎖"},

    # =========================================================================
    # МЕМНЫЕ / FUN
    # =========================================================================
    {"code": "TORPEDO",          "name": "Torpedo",              "description": "3+ столкновения за гонку", "icon": "🚇"},
    {"code": "GLASS_CANNON",     "name": "Glass Cannon",         "description": "Лучший круг + DNF в одной гонке", "icon": "🔮"},
    {"code": "REVERSE_GRID",     "name": "Reverse Grid",         "description": "Финишировал ниже стартовой позиции 5 раз подряд", "icon": "🔃"},
    {"code": "SUNDAY_DRIVER",    "name": "Sunday Driver",        "description": "Самый медленный круг среди людей 3 раза подряд", "icon": "🐌"},
    {"code": "LAST_NOT_LEAST",   "name": "Last but not Least",   "description": "Последний среди людей, но выше 10 AI", "icon": "🥉"},
    {"code": "JINXED",           "name": "Jinxed",               "description": "DNF 3 гонки подряд", "icon": "🫠"},
    {"code": "PHOENIX",          "name": "Phoenix",              "description": "После 3 DNF подряд — подиум", "icon": "🔥"},
    {"code": "GENTLEMAN",        "name": "Gentleman",            "description": "Ни одного столкновения за весь сезон (мин. 5 гонок)", "icon": "🎩"},

    # =========================================================================
    # ЭКСКЛЮЗИВНЫЕ
    # =========================================================================
    {"code": "FOUNDING_FATHER",  "name": "Founding Father",      "description": "Участник первой гонки в системе", "icon": "🏛"},
    {"code": "ARCHITECT",        "name": "Architect",             "description": "Создал лобби которое провело 10+ гонок", "icon": "🏗"},
    {"code": "POPULAR_CHOICE",   "name": "Popular Choice",       "description": "5+ людей играли в твоём лобби", "icon": "👥"},
]


async def seed_achievements(db) -> None:
    """Вставляет достижения в БД если их ещё нет."""
    from sqlalchemy import select
    from backend.models.models import Achievement

    for ach in ACHIEVEMENTS:
        existing = await db.execute(
            select(Achievement).where(Achievement.code == ach["code"])
        )
        if not existing.scalars().first():
            db.add(Achievement(**ach))

    await db.commit()
    print(f"[ACHIEVEMENTS] Seeded {len(ACHIEVEMENTS)} achievements")
