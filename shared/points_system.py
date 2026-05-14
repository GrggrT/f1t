# F1 points system — WDC + WCC calculator

POINTS_MAP: dict[int, float] = {
    1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
    6: 8,  7: 6,  8: 4,  9: 2,  10: 1,
}

FASTEST_LAP_POINTS = 1.0  # только если финишировал в топ-10


def calc_points(position: int, has_fastest_lap: bool = False, result_status: int = 3) -> float:
    """Считает очки для одного результата."""
    from shared.f1_mappings import FINISHED_STATUS
    if result_status not in FINISHED_STATUS:
        return 0.0
    pts = POINTS_MAP.get(position, 0.0)
    if has_fastest_lap and position <= 10:
        pts += FASTEST_LAP_POINTS
    return pts


def calc_wdc(results: list[dict]) -> list[dict]:
    """
    Принимает список результатов гонок.
    Каждый элемент: {driver_id, driver_name, team_id, team_name,
                     player_id, is_human, position, has_fastest_lap, result_status}
    Возвращает standings отсортированный по total_points DESC.
    """
    standings: dict[int, dict] = {}

    for r in results:
        did = r["driver_id"]
        if did not in standings:
            standings[did] = {
                "driver_id":    did,
                "driver_name":  r["driver_name"],
                "team_id":      r["team_id"],
                "team_name":    r["team_name"],
                "player_id":    r.get("player_id"),
                "is_human":     r.get("is_human", False),
                "total_points": 0.0,
                "wins":         0,
                "podiums":      0,
                "fastest_laps": 0,
                "dnfs":         0,
                "best_finish":  None,
            }
        entry = standings[did]
        pts = calc_points(r["position"], r.get("has_fastest_lap", False), r.get("result_status", 3))
        entry["total_points"] += pts

        pos = r["position"]
        if pos == 1:
            entry["wins"] += 1
        if pos <= 3:
            entry["podiums"] += 1
        if r.get("has_fastest_lap"):
            entry["fastest_laps"] += 1

        from shared.f1_mappings import is_dnf
        if is_dnf(r.get("result_status", 3)):
            entry["dnfs"] += 1

        if entry["best_finish"] is None or pos < entry["best_finish"]:
            entry["best_finish"] = pos

    sorted_standings = sorted(standings.values(), key=lambda x: (-x["total_points"], x["best_finish"] or 99))
    return sorted_standings


def calc_wcc(wdc_standings: list[dict]) -> list[dict]:
    """
    Считает WCC из готового WDC standings.
    Возвращает список команд отсортированный по total_points DESC.
    """
    teams: dict[int, dict] = {}

    for driver in wdc_standings:
        tid = driver["team_id"]
        if tid not in teams:
            teams[tid] = {
                "team_id":      tid,
                "team_name":    driver["team_name"],
                "total_points": 0.0,
                "wins":         0,
                "drivers":      [],
            }
        teams[tid]["total_points"] += driver["total_points"]
        teams[tid]["wins"]         += driver["wins"]
        teams[tid]["drivers"].append(driver["driver_name"])

    return sorted(teams.values(), key=lambda x: -x["total_points"])
