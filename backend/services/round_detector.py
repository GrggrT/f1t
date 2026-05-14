"""
Определяет номер раунда для trackId в текущем сезоне.
Логика из спецификации (раздел 6).
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.models import Race, Season


async def detect_round(
    db: AsyncSession,
    season_id: int,
    track_id: int,
    session_uid: int,
    raced_at: datetime | None = None,
) -> tuple[int | None, str]:
    """
    Возвращает (round_number, status).

    status:
    - "new"        — новый раунд для этого track
    - "duplicate"  — тот же session_uid уже в БД
    - "reconnect"  — та же трасса, тот же день, другой UID (<30 мин) → спросить
    - "new_season" — все трассы календаря пройдены
    """
    if raced_at is None:
        raced_at = datetime.now(timezone.utc)

    # Проверка дубля по session_uid
    dup_result = await db.execute(select(Race).where(Race.session_uid == session_uid))
    if dup_result.scalars().first():
        return None, "duplicate"

    # Загружаем сезон и его календарь
    season_result = await db.execute(select(Season).where(Season.id == season_id))
    season = season_result.scalars().first()
    if not season:
        return 1, "new"

    calendar: list[dict] = season.calendar or []

    # Гонки этого сезона
    races_result = await db.execute(
        select(Race).where(Race.season_id == season_id)
    )
    races = races_result.scalars().all()

    completed_track_ids = {r.track_id for r in races}

    # Проверяем реконнект: та же трасса уже есть в БД, тот же день, другой UID
    same_track_races = [r for r in races if r.track_id == track_id]
    if same_track_races:
        latest = max(same_track_races, key=lambda r: r.raced_at)
        time_diff = abs((raced_at - latest.raced_at.replace(tzinfo=timezone.utc)).total_seconds())
        if time_diff < 1800:  # 30 минут
            return None, "reconnect"

    # Определяем следующий round_number по календарю
    for entry in calendar:
        if entry["track_id"] == track_id and track_id not in completed_track_ids:
            return entry["round"], "new"

    # Если трасса в календаре но уже пройдена — это следующий сезон или вне календаря
    all_calendar_tracks = {e["track_id"] for e in calendar}
    if all_calendar_tracks and all_calendar_tracks.issubset(completed_track_ids):
        return None, "new_season"

    # Трасса не в календаре — назначаем следующий номер
    next_round = len(races) + 1
    return next_round, "new"
