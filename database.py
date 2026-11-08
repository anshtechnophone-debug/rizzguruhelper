"""SQLite persistence for personal group invite links."""
import sqlite3
from pathlib import Path

from config import DB_FILE


def db_connect() -> sqlite3.Connection:
    path = Path(DB_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db() -> None:
    with db_connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS personal_links (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                invite_link TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)


def save_link(chat_id: int, user_id: int, link: str) -> None:
    with db_connect() as db:
        db.execute("""
            INSERT INTO personal_links (chat_id, user_id, invite_link)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET invite_link = excluded.invite_link
        """, (chat_id, user_id, link))
