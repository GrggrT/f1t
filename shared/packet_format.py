# Adapter pattern для UDP форматов F1 2024 / 2025
# При выходе F1 26 — меняем только этот файл.

SUPPORTED_FORMATS = {2024, 2025}

# Packet IDs — одинаковы для 2024 и 2025
PACKET_IDS = {
    "MOTION":               0,
    "SESSION":              1,
    "LAP_DATA":             2,
    "EVENT":                3,
    "PARTICIPANTS":         4,
    "CAR_SETUPS":           5,
    "CAR_TELEMETRY":        6,
    "CAR_STATUS":           7,
    "CAR_DAMAGE":           8,
    "MOTION_EX":            9,
    "SESSION_HISTORY":      10,
    "FINAL_CLASSIFICATION": 11,
    "LAP_POSITIONS":        12,   # NEW in F1 25
    "TYRE_SETS":            13,
    "TIME_TRIAL":           14,
    "LOBBY_INFO":           15,
}

# Event codes (4-char string)
EVENT_CODES = {
    "SSTA": "Session Started",
    "SEND": "Session Ended",
    "FTLP": "Fastest Lap",
    "RTMT": "Retirement",
    "DRSE": "DRS Enabled",
    "DRSD": "DRS Disabled",
    "CHQF": "Chequered Flag",
    "PENA": "Penalty Issued",
    "SPTP": "Speed Trap",
    "STLG": "Start Lights",
    "LGOT": "Lights Out",
    "DTSV": "Drive Through Served",
    "SGSV": "Stop Go Served",
    "FLBK": "Flashback",
    "BUTN": "Button Status",
    "OVTK": "Overtake",
    "RDFL": "Red Flag",
    "C1SL": "Collision",
}

# Поля, которые менялись между форматами
# Ключ: поле; значение: {format: правило}
FIELD_QUIRKS = {
    # В F1 24 и ранее порядок m_driverStatus / m_gridPosition был перепутан
    # В F1 25 исправлен. Адаптер инвертирует для старых пакетов.
    "lap_data.driver_status_grid_position_swapped": {
        2024: True,
        2025: False,
    },
    # Длина имени участника
    "participants.name_length": {
        2024: 48,
        2025: 32,
    },
}


class PacketAdapter:
    """Нормализует поля пакета к единому формату независимо от версии протокола."""

    def __init__(self, packet_format: int):
        if packet_format not in SUPPORTED_FORMATS:
            # Принимаем, но логируем — лучше не упасть на старом пакете
            packet_format = max(SUPPORTED_FORMATS)
        self.fmt = packet_format

    def normalize_lap_data(self, raw: dict) -> dict:
        """Исправляет swap m_driverStatus / m_gridPosition для F1 24."""
        if not FIELD_QUIRKS["lap_data.driver_status_grid_position_swapped"].get(self.fmt, False):
            return raw

        for lap_entry in raw.get("m_lapData", []):
            if not isinstance(lap_entry, dict):
                continue
            lap_entry["m_driverStatus"], lap_entry["m_gridPosition"] = (
                lap_entry.get("m_gridPosition"),
                lap_entry.get("m_driverStatus"),
            )
        return raw

    def normalize_participant(self, raw: dict) -> dict:
        """Обрезает имя до правильной длины."""
        max_len = FIELD_QUIRKS["participants.name_length"].get(self.fmt, 32)
        participants = raw.get("m_participants")
        if isinstance(participants, list):
            for participant in participants:
                if isinstance(participant, dict) and isinstance(participant.get("m_name"), str):
                    participant["m_name"] = participant["m_name"][:max_len].rstrip("\x00")
            return raw

        if "m_name" in raw and isinstance(raw["m_name"], str):
            raw["m_name"] = raw["m_name"][:max_len].rstrip("\x00")
        return raw

    def normalize(self, packet_id: int, raw: dict) -> dict:
        if packet_id == PACKET_IDS["LAP_DATA"]:
            return self.normalize_lap_data(raw)
        if packet_id == PACKET_IDS["PARTICIPANTS"]:
            return self.normalize_participant(raw)
        return raw


def get_adapter(packet_format: int) -> PacketAdapter:
    return PacketAdapter(packet_format)
