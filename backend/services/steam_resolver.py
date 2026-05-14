"""
Резолвер Steam профилей.
Парсит любой формат ссылки → SteamID64 + текущий persona name.
Использует публичный XML эндпоинт Steam (без API ключа).
"""
import re
import xml.etree.ElementTree as ET
import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; F1LeagueBot/1.0)"}


def _normalize_url(raw: str) -> str | None:
    """
    Принимает любой формат:
      https://steamcommunity.com/id/Greg04i
      https://steamcommunity.com/profiles/76561198012345678
      steamcommunity.com/id/Greg04i
      76561198012345678   ← просто SteamID64
    Возвращает canonical URL для ?xml=1
    """
    raw = raw.strip().rstrip("/")

    # Просто SteamID64 (17 цифр)
    if re.fullmatch(r"\d{17}", raw):
        return f"https://steamcommunity.com/profiles/{raw}"

    # Уже полный URL
    if "steamcommunity.com" in raw:
        if not raw.startswith("http"):
            raw = "https://" + raw
        return raw

    # Vanity name без домена
    if re.fullmatch(r"[a-zA-Z0-9_-]+", raw):
        return f"https://steamcommunity.com/id/{raw}"

    return None


async def resolve_steam_profile(raw: str) -> dict | None:
    """
    Возвращает:
      {
        "steam_id64":   "76561198012345678",
        "persona_name": "Greg04i",         ← текущее имя в Steam
        "avatar_url":   "https://...",
        "profile_url":  "https://steamcommunity.com/id/Greg04i",
      }
    или None если не удалось.
    """
    url = _normalize_url(raw)
    if not url:
        return None

    xml_url = url + "/?xml=1"
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
            r = await client.get(xml_url)
        if r.status_code != 200:
            return None

        root = ET.fromstring(r.text)

        # Steam возвращает <error> если профиль закрыт или не найден
        error = root.findtext("error")
        if error:
            return None

        steam_id64   = root.findtext("steamID64")
        persona_name = root.findtext("steamID")        # persona name (отображаемое имя)
        avatar_url   = root.findtext("avatarFull") or root.findtext("avatarMedium")
        profile_url  = root.findtext("customURL")
        if profile_url:
            profile_url = f"https://steamcommunity.com/id/{profile_url}"
        else:
            profile_url = f"https://steamcommunity.com/profiles/{steam_id64}"

        if not steam_id64 or not persona_name:
            return None

        return {
            "steam_id64":   steam_id64,
            "persona_name": persona_name,
            "avatar_url":   avatar_url,
            "profile_url":  profile_url,
        }

    except Exception as e:
        print(f"[STEAM] resolve error for {raw!r}: {e}")
        return None


async def fetch_current_name(steam_id64: str) -> str | None:
    """Получает текущий persona name по SteamID64 (для проверки смены ника)."""
    result = await resolve_steam_profile(steam_id64)
    return result["persona_name"] if result else None
