import os
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION = os.getenv("TELETHON_SESSION", "userbot_session")
OWNER_ID = int(os.getenv("OWNER_ID", "1400038307"))
DB_FILE = os.getenv("USERBOT_DB_FILE", "userbot.db")
SCAN_INTERVAL = max(60, int(os.getenv("SCAN_INTERVAL", "300")))
DEFAULT_DM_COOLDOWN = max(60, int(os.getenv("DM_COOLDOWN", "86400")))
DEFAULT_DM_REPLY = os.getenv(
    "DEFAULT_DM_REPLY",
    "Thanks for your message! I may take a while to reply. "
    "For app information, visit https://play.google.com/store/apps/details?id=com.prothon.rizzguru",
)
if not API_ID or not API_HASH:
    raise RuntimeError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env.")
