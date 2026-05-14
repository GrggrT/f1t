"""Форматирует данные в красивый Telegram-текст (HTML parse mode)."""

WEATHER = ["☀️","🌤","☁️","🌧","⛈","🌩"]
TYRE_ICONS = {"C1":"⬜","C2":"⬜","C3":"🟡","C4":"🟠","C5":"🔴","Inter":"🟢","Wet":"🔵"}

STATUS_ICONS = {"Finished":"","DNF":"💥","DSQ":"🚫","Retired":"🔧","Not Classified":"—"}
PODIUM_MEDALS = {1:"🥇",2:"🥈",3:"🥉"}


def ms_to_laptime(ms: int | None) -> str:
    if not ms:
        return "—"
    s = ms / 1000
    m = int(s // 60)
    sec = s % 60
    return f"{m}:{sec:06.3f}" if m else f"{sec:.3f}s"


def fmt_race_results(race: dict) -> str:
    track  = race.get("track_name", "Unknown")
    round_ = race.get("round", "?")
    w_idx  = race.get("weather_start")
    weather = WEATHER[w_idx] if w_idx is not None and w_idx < len(WEATHER) else ""
    laps   = race.get("total_laps", "?")

    results = sorted(race.get("results", []), key=lambda r: r.get("position") or 99)
    human_count = sum(1 for r in results if r.get("is_human"))
    fl_driver = next((r for r in results if r.get("has_fastest_lap")), None)

    lines = [
        f"🏁 <b>{track}</b> — Round {round_} {weather}",
        f"<i>{laps} кругов · {human_count} участников</i>",
        "",
    ]

    for r in results:
        pos     = r.get("position")
        status  = r.get("result_status", "Finished")
        is_human = r.get("is_human", False)
        name    = r.get("driver_name", "?")
        team    = r.get("team_name", "?")
        pts     = r.get("points", 0)
        fl      = r.get("has_fastest_lap", False)

        # Иконка позиции
        if status not in ("Finished", "", None):
            pos_str = STATUS_ICONS.get(status, status)
        else:
            pos_str = PODIUM_MEDALS.get(pos, f"{pos}.")

        # Имя — выделяем людей жирным
        name_fmt = f"<b>{name}</b>" if is_human else name

        # Шины
        stints = r.get("tyre_stints") or []
        tyre_str = " ".join(
            TYRE_ICONS.get(s.get("compound",""), "○") for s in stints
        ) if stints else ""

        # FL
        fl_str = " 🟣" if fl else ""

        pts_str = f" <code>+{int(pts)}pt</code>" if pts > 0 else ""

        line = f"{pos_str} {name_fmt} · <i>{team}</i>{tyre_str}{fl_str}{pts_str}"
        lines.append(line)

    if fl_driver:
        fl_time = ms_to_laptime(fl_driver.get("best_lap_ms"))
        lines.append(f"\n🟣 Fastest Lap: <b>{fl_driver['driver_name']}</b> — {fl_time}")

    return "\n".join(lines)


def fmt_wdc_standings(standings: list[dict], title: str = "🏆 Drivers Championship") -> str:
    lines = [f"<b>{title}</b>", ""]
    for s in standings[:15]:
        pos      = s.get("position", "?")
        name     = s.get("driver_name", "?")
        team     = s.get("team_name", "?")
        pts      = s.get("total_points", 0)
        is_human = s.get("is_human", False)
        wins     = s.get("wins", 0)
        medal    = PODIUM_MEDALS.get(pos, "")

        name_fmt = f"<b>{name}</b>" if is_human else name
        wins_str = f" 🏆×{wins}" if wins else ""
        medal_str = f"{medal} " if medal else f"{pos}. "

        lines.append(f"{medal_str}{name_fmt} · <i>{team}</i>{wins_str} — <code>{int(pts)}</code>")

    # Показываем всех людей если они вне топ-15
    humans_outside = [s for s in standings[15:] if s.get("is_human")]
    if humans_outside:
        lines.append("…")
        for s in humans_outside:
            lines.append(f"{s['position']}. <b>{s['driver_name']}</b> · <i>{s['team_name']}</i> — <code>{int(s['total_points'])}</code>")

    return "\n".join(lines)


def fmt_wcc_standings(standings: list[dict]) -> str:
    lines = ["<b>🏗 Constructors Championship</b>", ""]
    for s in standings:
        pos    = s.get("position", "?")
        team   = s.get("team_name", "?")
        pts    = s.get("total_points", 0)
        d1     = s.get("driver_1") or ""
        d2     = s.get("driver_2") or ""
        medal  = PODIUM_MEDALS.get(pos, f"{pos}.")
        drivers = " + ".join(x for x in [d1, d2] if x)
        lines.append(f"{medal} <b>{team}</b>  {drivers} — <code>{int(pts)}</code>")
    return "\n".join(lines)


def fmt_player_stats(stats: dict) -> str:
    name   = stats.get("name", "?")
    pts    = stats.get("total_points", 0)
    races  = stats.get("races", 0)
    wins   = stats.get("wins", 0)
    pods   = stats.get("podiums", 0)
    dnfs   = stats.get("dnfs", 0)
    fl     = stats.get("fastest_laps", 0)
    avg    = stats.get("avg_position")
    best   = stats.get("best_finish")

    avg_str  = f"{avg:.1f}" if avg else "—"
    best_str = f"P{best}" if best else "—"

    history = stats.get("race_history", [])
    last5   = history[-5:] if len(history) >= 5 else history
    form    = " ".join(
        PODIUM_MEDALS.get(r.get("position"), str(r.get("position") or "?"))
        for r in last5
    )

    lines = [
        f"👤 <b>{name}</b>",
        "",
        f"⭐ Очков: <code>{int(pts)}</code>",
        f"🏎 Гонок: {races}",
        f"🥇 Побед: {wins}   🏆 Подиумов: {pods}",
        f"🟣 FL: {fl}   💥 DNF: {dnfs}",
        f"📊 Avg: {avg_str}   Best: {best_str}",
    ]
    if form:
        lines.append(f"Форма: {form}")

    return "\n".join(lines)


def fmt_calendar(calendar: list[dict]) -> str:
    done  = sum(1 for c in calendar if c.get("completed"))
    total = len(calendar)
    lines = [f"📅 <b>Календарь сезона</b>  ({done}/{total})", ""]

    for entry in calendar:
        round_  = entry.get("round", "?")
        track   = entry.get("track_name", "?")
        done_   = entry.get("completed", False)
        icon    = "✅" if done_ else "⬜"
        lines.append(f"{icon} R{round_} — {track}")

    return "\n".join(lines)
