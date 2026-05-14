import json
import os
from pathlib import Path

# Сервер
SERVER_URL  = os.getenv("F1_SERVER_URL",  "http://localhost:8000")
WS_URL      = os.getenv("F1_WS_URL",      "ws://localhost:8000/ws/agent")
AGENT_SECRET_TOKEN = os.getenv("AGENT_SECRET_TOKEN", "")
AUTH_TOKEN = os.getenv("F1_AUTH_TOKEN", "")
AGENT_MODE = os.getenv("F1_AGENT_MODE", "personal")
INVITE_TOKEN = os.getenv("F1_INVITE_TOKEN", "")
if not INVITE_TOKEN and not AGENT_SECRET_TOKEN:
    import warnings
    warnings.warn("F1_INVITE_TOKEN not set! Agent authentication is disabled.", stacklevel=2)


# Runtime override for AGENT_SECRET_TOKEN, settable via set_agent_token() so the
# launcher can rotate the token without restarting the whole agent process.
# Modules that need the current token must call get_agent_secret_token() rather
# than reading the AGENT_SECRET_TOKEN module constant.
_AGENT_TOKEN_OVERRIDE: str | None = None


def get_agent_secret_token() -> str:
    """Return the live AGENT_SECRET_TOKEN (override > env > "")."""
    if _AGENT_TOKEN_OVERRIDE is not None:
        return _AGENT_TOKEN_OVERRIDE
    return os.getenv("AGENT_SECRET_TOKEN", "")


class AuthFailureError(Exception):
    """Raised when the backend rejects AGENT_SECRET_TOKEN with HTTP 401.

    Delivery modules should not retry on this — the token will keep being
    rejected until the user enters a new one. The launcher catches it,
    surfaces the 'auth_rejected' event to the UI, and waits for set_agent_token().
    """


def set_agent_token(new_token: str) -> None:
    """Update AGENT_SECRET_TOKEN at runtime and persist to launcher_config.json.

    Called when the user re-enters a fresh token after the backend rejected
    the old one with 401. After this returns, the three delivery modules
    (uploader / telemetry_delivery / ws_client) will pick up the new token
    on their next attempt without needing a process restart.
    """
    global _AGENT_TOKEN_OVERRIDE
    cleaned = (new_token or "").strip()
    _AGENT_TOKEN_OVERRIDE = cleaned
    os.environ["AGENT_SECRET_TOKEN"] = cleaned

    config_file = Path.home() / "f1league_agent" / "launcher_config.json"
    config: dict = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            config = {}
    config["agent_token"] = cleaned
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

# UDP
UDP_HOST = "0.0.0.0"
UDP_PORT = int(os.getenv("F1_UDP_PORT", "20777"))

# Season (настраивается под текущий сезон)
SEASON_ID = int(os.getenv("F1_SEASON_ID", "1"))

# Локальные файлы
DATA_DIR = Path(os.getenv("F1_DATA_DIR", Path.home() / "f1league_agent"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE  = DATA_DIR / "final_classification_cache.json"
TELEMETRY_CACHE_FILE = DATA_DIR / "telemetry_flush_cache.json"
RAW_LOG_DIR = DATA_DIR / "raw_logs"
RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Retry
RETRY_DELAYS = [1, 5, 30]   # секунды между попытками

# Телеметрия (Phase 4)
TELEMETRY_ENABLED = True
TELEMETRY_HZ      = 3   # сэмплов в секунду
