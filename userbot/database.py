import sqlite3
from pathlib import Path
from .config import DB_FILE, DEFAULT_DM_COOLDOWN, DEFAULT_DM_REPLY

Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(DB_FILE)
db.row_factory = sqlite3.Row

def setup_database():
    db.executescript("""
        CREATE TABLE IF NOT EXISTS groups_list (
            group_id INTEGER PRIMARY KEY, title TEXT NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS dm_replies (user_id INTEGER PRIMARY KEY, last_reply REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS group_messages (
            group_id INTEGER PRIMARY KEY, message TEXT NOT NULL, updated_at REAL NOT NULL
        );
    """)
    defaults = {
        "dm_enabled": "1",
        "dm_reply": DEFAULT_DM_REPLY,
        "dm_cooldown": str(DEFAULT_DM_COOLDOWN),
        "last_scan": "0",
    }
    db.executemany("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", defaults.items())
    db.commit()

def get_setting(key, default=""):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    db.execute(
        """INSERT INTO settings(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (key, str(value)),
    )
    db.commit()
