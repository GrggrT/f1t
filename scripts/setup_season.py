"""
Скрипт первого запуска: создаёт Season 1 с календарём F1 2025.
Запускать ПОСЛЕ того как backend запущен:

  python scripts/setup_season.py
  или
  python scripts/setup_season.py --url http://YOUR_SERVER:8000
"""
import sys
import httpx
import argparse

# F1 2025 calendar (track_id из f1_mappings.py)
F1_2025_CALENDAR = [
    {"round": 1,  "track_id": 3,  "track_name": "Bahrain"},
    {"round": 2,  "track_id": 29, "track_name": "Saudi Arabia (Jeddah)"},
    {"round": 3,  "track_id": 0,  "track_name": "Australia (Melbourne)"},
    {"round": 4,  "track_id": 13, "track_name": "Japan (Suzuka)"},
    {"round": 5,  "track_id": 2,  "track_name": "China (Shanghai)"},
    {"round": 6,  "track_id": 30, "track_name": "Miami"},
    {"round": 7,  "track_id": 27, "track_name": "Emilia Romagna (Imola)"},
    {"round": 8,  "track_id": 5,  "track_name": "Monaco"},
    {"round": 9,  "track_id": 6,  "track_name": "Canada (Montreal)"},
    {"round": 10, "track_id": 4,  "track_name": "Spain (Catalunya)"},
    {"round": 11, "track_id": 17, "track_name": "Austria"},
    {"round": 12, "track_id": 7,  "track_name": "Great Britain (Silverstone)"},
    {"round": 13, "track_id": 9,  "track_name": "Hungary (Hungaroring)"},
    {"round": 14, "track_id": 10, "track_name": "Belgium (Spa)"},
    {"round": 15, "track_id": 26, "track_name": "Netherlands (Zandvoort)"},
    {"round": 16, "track_id": 11, "track_name": "Italy (Monza)"},
    {"round": 17, "track_id": 20, "track_name": "Azerbaijan (Baku)"},
    {"round": 18, "track_id": 12, "track_name": "Singapore"},
    {"round": 19, "track_id": 15, "track_name": "USA (COTA)"},
    {"round": 20, "track_id": 19, "track_name": "Mexico City"},
    {"round": 21, "track_id": 16, "track_name": "Brazil (Sao Paulo)"},
    {"round": 22, "track_id": 31, "track_name": "Las Vegas"},
    {"round": 23, "track_id": 32, "track_name": "Qatar (Losail)"},
    {"round": 24, "track_id": 14, "track_name": "Abu Dhabi"},
]

POINTS_SYSTEM = {
    "1": 25, "2": 18, "3": 15, "4": 12, "5": 10,
    "6": 8,  "7": 6,  "8": 4,  "9": 2,  "10": 1,
    "fastest_lap": 1
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--name", default="Season 1")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    print(f"Connecting to {base}...")

    # Health check
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        r.raise_for_status()
        print(f"✅ Backend is up: {r.json()}")
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        sys.exit(1)

    # Создаём сезон
    payload = {
        "name":          args.name,
        "calendar":      F1_2025_CALENDAR,
        "points_system": POINTS_SYSTEM,
    }

    try:
        r = httpx.post(f"{base}/api/admin/seasons", json=payload, timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"✅ Season created: ID={data['id']}, name='{data['name']}'")
            print(f"   {len(F1_2025_CALENDAR)} races in calendar")
            print(f"\n📝 Set in .env:  F1_SEASON_ID={data['id']}")
        else:
            print(f"❌ Failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print("\n🏎 Next steps:")
    print("  1. Register players: POST /api/players/register")
    print("  2. Or in Telegram: /register YourName")
    print("  3. Add steam names: /addsteam YourSteamName")
    print("  4. Start F1 25, launch agent, race!")


if __name__ == "__main__":
    main()
