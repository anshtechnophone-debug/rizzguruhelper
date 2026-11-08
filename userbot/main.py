import asyncio
import time
from telethon import TelegramClient, events, utils
from .config import API_ID, API_HASH, SESSION, SCAN_INTERVAL, DEFAULT_DM_COOLDOWN
from .database import db, get_setting, set_setting, setup_database

client = TelegramClient(SESSION, API_ID, API_HASH)

async def scan_groups():
    count = 0
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not (getattr(entity, "megagroup", False) or entity.__class__.__name__ == "Chat"):
            continue
        db.execute(
            """INSERT INTO groups_list(group_id, title, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
            title = excluded.title, updated_at = excluded.updated_at""",
            (utils.get_peer_id(entity), getattr(entity, "title", "Group"), time.time()),
        )
        count += 1
    db.commit()
    set_setting("last_scan", time.time())
    return count

async def scan_loop():
    while True:
        try:
            last = float(get_setting("last_scan", "0") or 0)
            if time.time() - last >= SCAN_INTERVAL:
                print(f"[SCAN] Saved {await scan_groups()} groups.")
        except Exception as exc:
            print(f"[SCAN ERROR] {exc}")
        await asyncio.sleep(15)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.(help|groups|replyon|replyoff|replyset|cooldown)(?:\s+([\s\S]*))?$"))
async def owner_commands(event):
    command = event.pattern_match.group(1)
    argument = (event.pattern_match.group(2) or "").strip()
    if command == "help":
        await event.respond(
            "Personal userbot commands\n"
            ".groups — show groups your account is already in\n"
            ".replyon / .replyoff — toggle DM auto-reply\n"
            ".replyset <text> — change the automatic reply\n"
            ".cooldown <hours> — set reply cooldown (minimum 1 hour)"
        )
    elif command == "groups":
        rows = db.execute("SELECT title FROM groups_list ORDER BY title COLLATE NOCASE LIMIT 100").fetchall()
        if not rows:
            await event.respond("No groups found yet. The scanner may still be running.")
        else:
            await event.respond("Groups found (up to 100):\n" + "\n".join(f"• {r['title']}" for r in rows))
    elif command == "replyon":
        set_setting("dm_enabled", "1")
        await event.respond("DM auto-reply enabled.")
    elif command == "replyoff":
        set_setting("dm_enabled", "0")
        await event.respond("DM auto-reply disabled.")
    elif command == "replyset":
        if not argument:
            await event.respond("Usage: .replyset Your automatic reply")
            return
        set_setting("dm_reply", argument)
        await event.respond("DM reply updated.")
    elif command == "cooldown":
        try:
            hours = float(argument)
            if hours < 1 or hours > 720:
                raise ValueError
            set_setting("dm_cooldown", int(hours * 3600))
            await event.respond(f"DM cooldown set to {hours:g} hours.")
        except ValueError:
            await event.respond("Usage: .cooldown 24 (1–720 hours).")

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def private_dm_autoreply(event):
    try:
        sender = await event.get_sender()
        if not sender or getattr(sender, "bot", False) or get_setting("dm_enabled", "1") != "1":
            return
        now = time.time()
        cooldown = max(3600, int(get_setting("dm_cooldown", str(DEFAULT_DM_COOLDOWN))))
        row = db.execute("SELECT last_reply FROM dm_replies WHERE user_id = ?", (sender.id,)).fetchone()
        if row and now - row["last_reply"] < cooldown:
            return
        reply = get_setting("dm_reply").strip()
        if not reply:
            return
        await event.respond(reply, link_preview=False)
        db.execute(
            """INSERT INTO dm_replies(user_id, last_reply) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_reply = excluded.last_reply""",
            (sender.id, now),
        )
        db.commit()
    except Exception as exc:
        print(f"[DM AUTO-REPLY ERROR] {exc}")

async def main():
    setup_database()
    await client.start()
    me = await client.get_me()
    print(f"[STARTED] Logged in as {me.username or me.id}")
    print("Send .help in Saved Messages.")
    print(f"[STARTUP] Found {await scan_groups()} groups.")
    asyncio.create_task(scan_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        db.close()
