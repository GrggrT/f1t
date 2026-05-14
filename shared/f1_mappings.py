# F1 25 mappings: trackId, teamId, driverId → names, colors
# ⚠️ Team/Driver IDs — верифицировать при первом запуске F1 25 (agent auto-scan)

# ---------------------------------------------------------------------------
# TRACKS
# ---------------------------------------------------------------------------

TRACKS: dict[int, str] = {
    0:  "Melbourne",
    1:  "Paul Ricard",
    2:  "Shanghai",
    3:  "Sakhir (Bahrain)",
    4:  "Catalunya",
    5:  "Monaco",
    6:  "Montreal",
    7:  "Silverstone",
    8:  "Hockenheim",
    9:  "Hungaroring",
    10: "Spa",
    11: "Monza",
    12: "Singapore",
    13: "Suzuka",
    14: "Abu Dhabi",
    15: "Texas (COTA)",
    16: "Brazil",
    17: "Austria",
    18: "Sochi",
    19: "Mexico",
    20: "Baku (Azerbaijan)",
    21: "Sakhir Short",
    22: "Silverstone Short",
    23: "Texas Short",
    24: "Suzuka Short",
    25: "Hanoi",
    26: "Zandvoort",
    27: "Imola",
    28: "Portimao",
    29: "Jeddah",
    30: "Miami",
    31: "Las Vegas",
    32: "Losail (Qatar)",
}

# ---------------------------------------------------------------------------
# TEAMS  (ID: F1 teamId)
# ---------------------------------------------------------------------------

TEAMS: dict[int, dict] = {
    0: {"name": "Mercedes",     "short": "MER", "color": "#27f4d2", "accent": "#4fffdd"},
    1: {"name": "Ferrari",      "short": "FER", "color": "#e10600", "accent": "#ff3030"},
    2: {"name": "Red Bull",     "short": "RBR", "color": "#3671c6", "accent": "#5590e0"},
    3: {"name": "Williams",     "short": "WIL", "color": "#64c4ff", "accent": "#88ddff"},
    4: {"name": "Aston Martin", "short": "AMR", "color": "#229971", "accent": "#33bb88"},
    5: {"name": "Alpine",       "short": "ALP", "color": "#0093cc", "accent": "#22aadd"},
    6: {"name": "RB",           "short": "RB",  "color": "#6692ff", "accent": "#88aaff"},
    7: {"name": "Haas",         "short": "HAA", "color": "#b6babd", "accent": "#cccfd2"},
    8: {"name": "McLaren",      "short": "MCL", "color": "#ff8000", "accent": "#ffaa44"},
    9: {"name": "Sauber",       "short": "SAU", "color": "#52e252", "accent": "#77ff77"},
}

# ---------------------------------------------------------------------------
# DRIVERS  (ID: F1 driverId)
# ---------------------------------------------------------------------------

DRIVERS: dict[int, dict] = {
    1:  {"name": "Hamilton",    "short": "HAM", "number": 44, "team_id": 0},
    4:  {"name": "Norris",      "short": "NOR", "number": 4,  "team_id": 8},
    6:  {"name": "Räikkönen",   "short": "RAI", "number": 7,  "team_id": 9},
    7:  {"name": "Räikkönen",   "short": "RAI", "number": 7,  "team_id": 9},  # duplicate guard
    14: {"name": "Alonso",      "short": "ALO", "number": 14, "team_id": 4},
    17: {"name": "Leclerc",     "short": "LEC", "number": 16, "team_id": 1},
    18: {"name": "Verstappen",  "short": "VER", "number": 1,  "team_id": 2},
    19: {"name": "Massa",       "short": "MAS", "number": 19, "team_id": 3},
    20: {"name": "Sainz",       "short": "SAI", "number": 55, "team_id": 1},
    22: {"name": "Button",      "short": "BUT", "number": 22, "team_id": 7},
    25: {"name": "Antonelli",   "short": "ANT", "number": 12, "team_id": 0},
    31: {"name": "Ocon",        "short": "OCO", "number": 31, "team_id": 5},
    33: {"name": "Verstappen",  "short": "VER", "number": 1,  "team_id": 2},  # old id guard
    35: {"name": "Lawson",      "short": "LAW", "number": 30, "team_id": 6},
    36: {"name": "Bearman",     "short": "BEA", "number": 87, "team_id": 7},
    38: {"name": "Gasly",       "short": "GAS", "number": 10, "team_id": 5},
    40: {"name": "Colapinto",   "short": "COL", "number": 43, "team_id": 3},
    41: {"name": "Hadjar",      "short": "HAD", "number": 22, "team_id": 6},
    43: {"name": "Piastri",     "short": "PIA", "number": 81, "team_id": 8},
    44: {"name": "Russell",     "short": "RUS", "number": 63, "team_id": 0},
    45: {"name": "Stroll",      "short": "STR", "number": 18, "team_id": 4},
    55: {"name": "Sainz",       "short": "SAI", "number": 55, "team_id": 1},  # old id guard
    63: {"name": "Russell",     "short": "RUS", "number": 63, "team_id": 0},  # old id guard
    81: {"name": "Piastri",     "short": "PIA", "number": 81, "team_id": 8},  # old id guard
    # F1 25 может добавить новые IDs — auto-scan при первой гонке
}

# ---------------------------------------------------------------------------
# SESSION TYPES
# ---------------------------------------------------------------------------

SESSION_TYPES: dict[int, str] = {
    0:  "Unknown",
    1:  "Practice 1",
    2:  "Practice 2",
    3:  "Practice 3",
    4:  "Short Practice",
    5:  "Qualifying 1",
    6:  "Qualifying 2",
    7:  "Qualifying 3",
    8:  "Short Qualifying",
    9:  "One Shot Qualifying",
    10: "Race",
    11: "Race 2",
    12: "Time Trial",
    13: "Sprint Shootout",
    14: "Sprint Race",
}

RACE_SESSION_TYPES = {10, 11}  # только эти пишем в БД
QUALI_SESSION_TYPES = {5, 6, 7, 8, 9}

# ---------------------------------------------------------------------------
# WEATHER
# ---------------------------------------------------------------------------

WEATHER: dict[int, str] = {
    0: "Clear",
    1: "Light Cloud",
    2: "Overcast",
    3: "Light Rain",
    4: "Heavy Rain",
    5: "Storm",
}

# ---------------------------------------------------------------------------
# TYRE COMPOUNDS
# ---------------------------------------------------------------------------

TYRE_COMPOUNDS: dict[int, str] = {
    16: "C1", 17: "C2", 18: "C3", 19: "C4", 20: "C5",
    7:  "Inter",
    8:  "Wet",
    9:  "Dry (Classic)",
    10: "Wet (Classic)",
    11: "Super Soft", 12: "Soft", 13: "Medium", 14: "Hard",
}

TYRE_VISUAL: dict[int, str] = {
    16: "Hard", 17: "Medium", 18: "Soft",
    7:  "Inter", 8: "Wet",
}

# ---------------------------------------------------------------------------
# RESULT STATUS
# ---------------------------------------------------------------------------

RESULT_STATUS: dict[int, str] = {
    0: "Invalid",
    1: "Inactive",
    2: "Active",
    3: "Finished",
    4: "DNF",
    5: "DSQ",
    6: "Retired",
    7: "Not Classified",
}

FINISHED_STATUS = {3}
DNF_STATUSES    = {4, 6}
DSQ_STATUS      = {5}

# ---------------------------------------------------------------------------
# PENALTIES
# ---------------------------------------------------------------------------

PENALTY_TYPES: dict[int, str] = {
    0:  "Drive Through",
    1:  "Stop Go",
    2:  "Grid Penalty",
    3:  "Penalty Reminder",
    4:  "Time Penalty",
    5:  "Warning",
    6:  "Disqualified",
    7:  "Removed from Formation Lap",
    8:  "Parked Too Long Timer",
    9:  "Tyre Regulations",
    10: "This Lap Invalidated",
    11: "This And Next Lap Invalidated",
    12: "This Lap Invalidated Without Reason",
    13: "This And Next Lap Invalidated Without Reason",
    14: "This And Previous Lap Invalidated",
    15: "This And Previous Lap Invalidated Without Reason",
    16: "Retired",
    17: "Black Flag Timer",
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_track_name(track_id: int) -> str:
    return TRACKS.get(track_id, f"Track #{track_id}")

def get_team(team_id: int) -> dict:
    return TEAMS.get(team_id, {"name": f"Team #{team_id}", "short": "???", "color": "#888888", "accent": "#aaaaaa"})

def get_driver(driver_id: int) -> dict:
    return DRIVERS.get(driver_id, {"name": f"Driver #{driver_id}", "short": "???", "number": 0, "team_id": -1})

def get_team_color(team_id: int) -> str:
    return get_team(team_id)["color"]

def get_session_type_name(session_type: int) -> str:
    return SESSION_TYPES.get(session_type, f"Session #{session_type}")

def is_race_session(session_type: int) -> bool:
    return session_type in RACE_SESSION_TYPES

def get_tyre_name(compound_id: int) -> str:
    return TYRE_COMPOUNDS.get(compound_id, f"Compound #{compound_id}")

def get_result_status_name(status: int) -> str:
    return RESULT_STATUS.get(status, f"Status #{status}")

def is_finished(status: int) -> bool:
    return status in FINISHED_STATUS

def is_dnf(status: int) -> bool:
    return status in DNF_STATUSES
