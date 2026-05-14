"""
Fun Stats — генерирует статистические «номинации» после каждых 4 гонок.
Расширенная версия: 15+ категорий.
"""
from __future__ import annotations
import statistics
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from backend.db.base import get_database_url
from backend.models.models import Race, RaceResult, RaceEvent, Player


async def compute_fun_stats(season_id: int) -> list[dict] | None:
    engine = create_async_engine(get_database_url(), echo=False)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sf() as db:
            races_res = await db.execute(
                select(Race).where(Race.season_id == season_id).order_by(Race.round_number)
            )
            races = races_res.scalars().all()

            if not races or len(races) % 4 != 0:
                return None

            race_ids = [r.id for r in races]

            results_res = await db.execute(
                select(RaceResult, Player.name.label("player_name"))
                .join(Player, Player.id == RaceResult.player_id, isouter=True)
                .where(RaceResult.race_id.in_(race_ids), RaceResult.is_human == True)  # noqa
            )
            rows = results_res.all()

            events_res = await db.execute(
                select(RaceEvent).where(RaceEvent.race_id.in_(race_ids))
            )
            events = events_res.scalars().all()
    finally:
        await engine.dispose()

    if not rows:
        return None

    # Группируем по player_id
    players: dict[int, dict] = {}
    for rr, pname in rows:
        pid = rr.player_id
        if pid not in players:
            players[pid] = {
                "name":           pname or f"Player#{pid}",
                "positions":      [],
                "grid_positions": [],
                "points":         [],
                "penalties":      0,
                "overtakes":      0,
                "pit_stops":      0,
                "dnfs":           0,
                "fl_count":       0,
                "best_laps_ms":   [],
                "grid_deltas":    [],
                "results":        [],  # (position, grid, race_id)
            }
        p = players[pid]
        if rr.position:
            p["positions"].append(rr.position)
        if rr.grid_position:
            p["grid_positions"].append(rr.grid_position)
        p["points"].append(rr.points)
        p["penalties"] += (rr.num_penalties or 0)
        p["pit_stops"] += (rr.num_pit_stops or 0)
        p["dnfs"]      += 1 if rr.result_status in (4, 6) else 0
        p["fl_count"]  += 1 if rr.has_fastest_lap else 0
        if rr.best_lap_ms:
            p["best_laps_ms"].append(rr.best_lap_ms)
        if rr.grid_position and rr.position:
            p["grid_deltas"].append(rr.grid_position - rr.position)
        p["results"].append((rr.position, rr.grid_position, rr.race_id))

    # Обгоны из событий
    overtake_counts: dict[int, int] = {}
    for ev in events:
        if ev.event_code == "OVTK":
            vidx = (ev.event_data or {}).get("overtakingVehicleIdx")
            if vidx is not None:
                overtake_counts[vidx] = overtake_counts.get(vidx, 0) + 1

    last_race_results = [rr for rr, _ in rows if rr.race_id == race_ids[-1]]
    vidx_to_pid = {rr.vehicle_index: rr.player_id for rr in last_race_results if rr.player_id}
    for vidx, cnt in overtake_counts.items():
        pid = vidx_to_pid.get(vidx)
        if pid and pid in players:
            players[pid]["overtakes"] += cnt

    # ---------------------------------------------------------------------------
    # Номинации
    # ---------------------------------------------------------------------------
    stats = []

    # 1. Mr. Consistent — минимальное стандартное отклонение позиций
    consistent = {
        pid: statistics.stdev(d["positions"]) if len(d["positions"]) > 1 else 0
        for pid, d in players.items() if d["positions"]
    }
    if consistent:
        mr_c = min(consistent, key=consistent.get)
        stats.append({
            "title": "Mr. Consistent", "icon": "🎯",
            "winner_name": players[mr_c]["name"],
            "value": f"σ={consistent[mr_c]:.1f} pos",
        })

    # 2. Американские горки — максимальный разброс
    if consistent:
        mr_chaos = max(consistent, key=consistent.get)
        stats.append({
            "title": "Американские горки", "icon": "🎢",
            "winner_name": players[mr_chaos]["name"],
            "value": f"σ={consistent[mr_chaos]:.1f} pos",
        })

    # 3. Король обгонов
    ot_leaders = [(pid, d["overtakes"]) for pid, d in players.items() if d["overtakes"] > 0]
    if ot_leaders:
        ot_winner = max(ot_leaders, key=lambda x: x[1])
        stats.append({
            "title": "Король обгонов", "icon": "💨",
            "winner_name": players[ot_winner[0]]["name"],
            "value": f"{ot_winner[1]} обгонов",
        })

    # 4. Штрафник сезона
    pen_leaders = [(pid, d["penalties"]) for pid, d in players.items() if d["penalties"] > 0]
    if pen_leaders:
        pen_winner = max(pen_leaders, key=lambda x: x[1])
        stats.append({
            "title": "Штрафник сезона", "icon": "🚨",
            "winner_name": players[pen_winner[0]]["name"],
            "value": f"{pen_winner[1]} штрафов",
        })

    # 5. Pit Stop King
    pit_leaders = [(pid, d["pit_stops"]) for pid, d in players.items() if d["pit_stops"] > 0]
    if pit_leaders:
        pit_winner = max(pit_leaders, key=lambda x: x[1])
        stats.append({
            "title": "Pit Stop King", "icon": "🔧",
            "winner_name": players[pit_winner[0]]["name"],
            "value": f"{pit_winner[1]} пит-стопов",
        })

    # 6. Fastest Lap Hunter
    fl_leaders = [(pid, d["fl_count"]) for pid, d in players.items() if d["fl_count"] > 0]
    if fl_leaders:
        fl_winner = max(fl_leaders, key=lambda x: x[1])
        stats.append({
            "title": "Fastest Lap Hunter", "icon": "🟣",
            "winner_name": players[fl_winner[0]]["name"],
            "value": f"{fl_winner[1]} быстрых кругов",
        })

    # 7. DNF Lord
    dnf_leaders = [(pid, d["dnfs"]) for pid, d in players.items() if d["dnfs"] > 0]
    if dnf_leaders:
        dnf_winner = max(dnf_leaders, key=lambda x: x[1])
        stats.append({
            "title": "DNF Lord", "icon": "💥",
            "winner_name": players[dnf_winner[0]]["name"],
            "value": f"{dnf_winner[1]} сходов",
        })

    # ---- NEW STATS ----

    # 8. Ракетный старт — наибольший средний прирост позиций
    delta_avgs = {
        pid: sum(d["grid_deltas"]) / len(d["grid_deltas"])
        for pid, d in players.items() if d["grid_deltas"]
    }
    if delta_avgs:
        rocket_pid = max(delta_avgs, key=delta_avgs.get)
        val = delta_avgs[rocket_pid]
        stats.append({
            "title": "Ракетный старт", "icon": "🚀",
            "winner_name": players[rocket_pid]["name"],
            "value": f"+{val:.1f} позиций в среднем" if val > 0 else f"{val:.1f} позиций в среднем",
        })

    # 9. Бетонная стена — наименьший |delta|
    abs_delta = {
        pid: abs(sum(d["grid_deltas"]) / len(d["grid_deltas"]))
        for pid, d in players.items() if d["grid_deltas"]
    }
    if abs_delta:
        wall_pid = min(abs_delta, key=abs_delta.get)
        stats.append({
            "title": "Бетонная стена", "icon": "🧱",
            "winner_name": players[wall_pid]["name"],
            "value": f"Δ={abs_delta[wall_pid]:.1f} позиций",
        })

    # 10. Тайм-аттакер — минимальный разброс времён кругов
    lap_consistency = {}
    for pid, d in players.items():
        if len(d["best_laps_ms"]) > 1:
            lap_consistency[pid] = statistics.stdev(d["best_laps_ms"])
    if lap_consistency:
        ta_pid = min(lap_consistency, key=lap_consistency.get)
        stats.append({
            "title": "Тайм-аттакер", "icon": "⏱",
            "winner_name": players[ta_pid]["name"],
            "value": f"σ={lap_consistency[ta_pid]/1000:.2f}с",
        })

    # 11. Поул-хантер — больше P1 на гриде
    pole_counts = {
        pid: sum(1 for g in d["grid_positions"] if g == 1)
        for pid, d in players.items()
    }
    pole_leaders = [(pid, c) for pid, c in pole_counts.items() if c > 0]
    if pole_leaders:
        pole_winner = max(pole_leaders, key=lambda x: x[1])
        stats.append({
            "title": "Поул-хантер", "icon": "🎯",
            "winner_name": players[pole_winner[0]]["name"],
            "value": f"{pole_winner[1]} поулов",
        })

    # 12. Камбэк-артист — наибольшее суммарное количество набранных позиций
    total_gains = {
        pid: sum(max(0, d) for d in data["grid_deltas"])
        for pid, data in players.items() if data["grid_deltas"]
    }
    if total_gains:
        cb_pid = max(total_gains, key=total_gains.get)
        if total_gains[cb_pid] > 0:
            stats.append({
                "title": "Камбэк-артист", "icon": "🎭",
                "winner_name": players[cb_pid]["name"],
                "value": f"+{total_gains[cb_pid]} позиций набрано",
            })

    # 13. Терминатор — больше AI позади себя в среднем
    # Simplified: avg position closer to 1 = more AI behind
    avg_positions = {
        pid: sum(d["positions"]) / len(d["positions"])
        for pid, d in players.items() if d["positions"]
    }
    if avg_positions:
        term_pid = min(avg_positions, key=avg_positions.get)
        ai_behind = 20 - avg_positions[term_pid]
        stats.append({
            "title": "Терминатор", "icon": "🤖",
            "winner_name": players[term_pid]["name"],
            "value": f"~{ai_behind:.0f} AI позади в среднем",
        })

    # 14. Хвост пелотона — самый медленный средний лучший круг
    avg_laps = {
        pid: sum(d["best_laps_ms"]) / len(d["best_laps_ms"])
        for pid, d in players.items() if d["best_laps_ms"]
    }
    if avg_laps:
        slow_pid = max(avg_laps, key=avg_laps.get)
        secs = avg_laps[slow_pid] / 1000
        stats.append({
            "title": "Хвост пелотона", "icon": "🐢",
            "winner_name": players[slow_pid]["name"],
            "value": f"{secs:.1f}с средний лучший круг",
        })

    # 15. Ледяной — ни разу не потерял позицию на первом круге
    # Approximated: grid_delta >= 0 for all races
    ice_candidates = [
        pid for pid, d in players.items()
        if d["grid_deltas"] and all(gd >= 0 for gd in d["grid_deltas"])
    ]
    if ice_candidates:
        # Pick the one with most races (more impressive)
        ice_pid = max(ice_candidates, key=lambda pid: len(players[pid]["grid_deltas"]))
        stats.append({
            "title": "Ледяной", "icon": "🧊",
            "winner_name": players[ice_pid]["name"],
            "value": f"Ни разу не потерял позицию ({len(players[ice_pid]['grid_deltas'])} гонок)",
        })

    return stats if stats else None
