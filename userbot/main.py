import asyncio
import io
import time
import csv

from telethon import TelegramClient, events, utils
from telethon.errors import FloodWaitError

from .config import API_ID, API_HASH, SESSION, SCAN_INTERVAL, DEFAULT_DM_COOLDOWN, OWNER_ID
from .database import db, get_setting, set_setting, setup_database

client = TelegramClient(SESSION, API_ID, API_HASH)
BROADCAST_LOCK = asyncio.Lock()


async def scan_groups():
    count = 0
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not (getattr(entity, "megagroup", False) or entity.__class__.__name__ == "Chat"):
            continue
        db.execute(
            """INSERT INTO groups_list(group_id, title, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at""",
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


HELP = (
    "RizzGuru Helper controls (owner DM)\n\n"
    ".help — show this help\n"
    ".start 3 <message> — post to groups where your account is an admin\n"
    ".setreply <message> — set the automatic DM reply\n"
    ".groups — show group status\n"
    ".getgc — create a file with group names and invite links\n\n"
)


def parse_campaign(argument, minimum=3):
    try:
        delay_text, message = argument.split(maxsplit=1)
        delay = float(delay_text)
        if not minimum <= delay <= 3600 or not message or len(message) > 4000:
            raise ValueError
        return delay, message
    except ValueError:
        return None


@client.on(events.NewMessage(incoming=True, pattern=r"^\.(help|groups|setreply|getgc|start|startdm)(?:\s+([\s\S]*))?$"))
async def owner_commands(event):
    if not event.is_private or event.sender_id != OWNER_ID:
        return
    command = event.pattern_match.group(1)
    argument = (event.pattern_match.group(2) or "").strip()

    if command == "help":
        await event.respond(HELP)
        return

    if command == "setreply":
        if not argument:
            await event.respond("Usage: .setreply <automatic reply text>")
            return
        set_setting("dm_reply", argument)
        await event.respond("Automatic DM reply updated.")
        return

    if command == "groups":
        rows = db.execute("SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE").fetchall()
        if not rows:
            await event.respond("No groups found. The scanner may still be running.")
            return
        lines = []
        for row in rows:
            status = "saved"
            try:
                entity = await client.get_entity(row["group_id"])
                me = await client.get_me()
                perms = await client.get_permissions(entity, me)
                status = "admin" if (getattr(perms, "is_admin", False) or getattr(perms, "is_creator", False)) else "member"
            except Exception as exc:
                status = f"unavailable ({type(exc).__name__})"
            lines.append(f"• {row['title']} | {row['group_id']} | {status}")
        await event.respond("Groups status:\n" + "\n".join(lines[:100]))
        return

    if command == "getgc":
        rows = db.execute("SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE").fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Group name", "Group ID", "Invite link", "Status"])
        for row in rows:
            title = row["title"] or str(row["group_id"])
            try:
                entity = await client.get_entity(row["group_id"])
                link = getattr(entity, "username", None)
                if link:
                    link = f"https://t.me/{link}"
                else:
                    link = await client.export_chat_invite_link(entity)
                writer.writerow([title, row["group_id"], link, "OK"])
            except Exception as exc:
                writer.writerow([title, row["group_id"], "", f"Unavailable: {type(exc).__name__}"])
        payload = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        payload.name = "rizzguru_groups.csv"
        await event.respond("Group list attached. Invite links may be unavailable where your account lacks permission.")
        await client.send_file(event.chat_id, payload, caption="Group names, IDs, invite links and status")
        return

    if command == "start":
        parsed = parse_campaign(argument)
        if not parsed:
            await event.respond(f"Usage: .{command} <seconds> <message> (3–3600 seconds; message up to 4000 characters).")
            return
        delay, message = parsed
        if BROADCAST_LOCK.locked():
            await event.respond("An announcement is already running.")
            return

        rows = db.execute("SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE").fetchall()
        eligible = []
        for row in rows:
            try:
                entity = await client.get_entity(row["group_id"])
                me = await client.get_me()
                permissions = await client.get_permissions(entity, me)
                if getattr(permissions, "is_admin", False) or getattr(permissions, "is_creator", False):
                    eligible.append((entity, row["title"] or str(row["group_id"])))
            except Exception:
                continue
        if not eligible:
            await event.respond("No groups where your account has admin/creator permissions.")
            return
        async with BROADCAST_LOCK:
            await event.respond(f"Starting group announcement in {len(eligible)} admin groups, with {delay:g}s delay.")
            sent, failed = 0, 0
            for i, (entity, title) in enumerate(eligible):
                try:
                    await client.send_message(entity, message, link_preview=False)
                    sent += 1
                except FloodWaitError as exc:
                    await asyncio.sleep(exc.seconds)
                    try:
                        await client.send_message(entity, message, link_preview=False)
                        sent += 1
                    except Exception:
                        failed += 1
                except Exception:
                    failed += 1
                if i < len(eligible) - 1:
                    await asyncio.sleep(delay)
            await event.respond(f"Group announcement complete. Sent: {sent}; failed: {failed}; total: {len(eligible)}.")
        return





@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def private_dm_autoreply(event):
    try:
        sender = await event.get_sender()
        if not sender or sender.id == OWNER_ID or getattr(sender, "bot", False):
            return
        now = time.time()
        cooldown = max(3600, int(get_setting("dm_cooldown", str(DEFAULT_DM_COOLDOWN))))
        row = db.execute("SELECT last_reply FROM dm_replies WHERE user_id=?", (sender.id,)).fetchone()
        if row and now - row["last_reply"] < cooldown:
            return
        reply = (get_setting("dm_reply") or "").strip()
        if not reply:
            return
        await event.respond(reply, link_preview=False)
        db.execute(
            "INSERT INTO dm_replies(user_id, last_reply) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_reply=excluded.last_reply",
            (sender.id, now),
        )
        db.commit()
    except Exception as exc:
        print(f"[DM AUTO-REPLY ERROR] {type(exc).__name__}: {exc}")


async def main():
    setup_database()
    await client.start()
    me = await client.get_me()
    print(f"[STARTED] Logged in as {me.username or me.id}; owner ID: {OWNER_ID}")
    count = await scan_groups()
    print(f"[STARTUP] Found {count} groups.")
    try:
        await client.send_message(OWNER_ID, f"Userbot online as {me.username or me.id}. Groups scanned: {count}. Send .help.")
    except Exception as exc:
        print(f"[OWNER NOTIFICATION ERROR] {type(exc).__name__}: {exc}")
    asyncio.create_task(scan_loop())
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        db.close()
