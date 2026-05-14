import os

BOT_TOKEN          = os.getenv("BOT_TOKEN", "")
API_URL            = os.getenv("API_URL", "http://localhost:8000")
SEASON_ID          = int(os.getenv("F1_SEASON_ID", "1"))
CHAT_ID            = int(os.getenv("TG_CHAT_ID", "0"))   # ID группового чата
ADMIN_IDS          = set(map(int, os.getenv("TG_ADMIN_IDS", "").split(",") if os.getenv("TG_ADMIN_IDS") else []))
BOT_NOTIFY_SECRET  = os.getenv("BOT_NOTIFY_SECRET", "internal-secret")
