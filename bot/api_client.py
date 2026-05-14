"""HTTP клиент для запросов к FastAPI backend из бота."""
import httpx
from bot.config import API_URL, SEASON_ID


async def get(path: str) -> dict | list | None:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{API_URL}{path}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[API] GET {path} error: {e}")
            return None


async def post(path: str, data: dict) -> dict | None:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(f"{API_URL}{path}", json=data)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[API] POST {path} error: {e}")
            return None


async def get_standings() -> list:
    return await get(f"/api/standings/{SEASON_ID}") or []

async def get_constructors() -> list:
    return await get(f"/api/constructors/{SEASON_ID}") or []

async def get_last_race() -> dict | None:
    races = await get(f"/api/races/{SEASON_ID}")
    if not races:
        return None
    last = sorted(races, key=lambda r: r["round"])[-1]
    return await get(f"/api/race/{last['id']}")

async def get_race(race_id: int) -> dict | None:
    return await get(f"/api/race/{race_id}")

async def get_player_stats(player_id: int) -> dict | None:
    return await get(f"/api/player/{player_id}/stats")

async def get_calendar() -> list:
    return await get(f"/api/calendar/{SEASON_ID}") or []
