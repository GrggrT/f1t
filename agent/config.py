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
