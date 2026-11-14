import asyncio
import time

from telethon import TelegramClient, events, utils
from telethon.errors import FloodWaitError

from .config import API_ID, API_HASH, SESSION, SCAN_INTERVAL, DEFAULT_DM_COOLDOWN, OWNER_ID
from .database import db, get_setting, set_setting, setup_database

client = TelegramClient(SESSION, API_ID, API_HASH)
LAST_GROUP_SEND = 0.0
GROUP_SEND_INTERVAL = 30
BROADCAST_LOCK = asyncio.Lock()


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


@client.on(events.NewMessage(incoming=True, pattern=r"^\.(help|groups|replyon|replyoff|replyset|dmview|cooldown|status|groupset|groupview|groupsend|groupclear|start|dmstart)(?:\s+([\s\S]*))?$"))
async def owner_commands(event):
    # Accept commands only in a private chat from the configured owner account.
    if not event.is_private or event.sender_id != OWNER_ID:
        return

    global LAST_GROUP_SEND
    command = event.pattern_match.group(1)
    argument = (event.pattern_match.group(2) or "").strip()

    if command == "help":
        await event.respond(
            "Personal userbot controls (owner private chat)\n"
            ".groups — list groups your account already joined\n"
            ".replyon / .replyoff — toggle DM auto-reply\n"
            ".replyset <text> — change the automatic DM reply\n"
            ".dmview — preview the current DM reply\n"
            ".cooldown <hours> — set DM reply cooldown (1–720)\n"
            ".status — show current settings\n"
            ".groupset <group_id> <text> — save a message for one group\n"
            ".groupview — view saved group messages\n"
            ".groupsend <group_id> — send that saved message to one group\n"
            ".groupclear <group_id> — delete that group's saved message\n"
            ".start <seconds> <message> — send an announcement to saved groups\n"
            ".dmstart <seconds> <message> — message users who have previously messaged you"
        )
    elif command == "groups":
        rows = db.execute(
            "SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE LIMIT 100"
        ).fetchall()
        if not rows:
            await event.respond("No groups found yet. The scanner may still be running.")
        else:
            lines = [f"• {r['title']} — ID: {r['group_id']}" for r in rows]
            await event.respond("Groups found (up to 100):\n" + "\n".join(lines))
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
    elif command == "dmview":
        await event.respond("Current DM reply:\n\n" + (get_setting("dm_reply") or "(empty)"))
    elif command == "cooldown":
        try:
            hours = float(argument)
            if hours < 1 or hours > 720:
                raise ValueError
            set_setting("dm_cooldown", int(hours * 3600))
            await event.respond(f"DM cooldown set to {hours:g} hours.")
        except ValueError:
            await event.respond("Usage: .cooldown 24 (1–720 hours).")
    elif command == "status":
        enabled = "ON" if get_setting("dm_enabled", "1") == "1" else "OFF"
        cooldown = int(get_setting("dm_cooldown", str(DEFAULT_DM_COOLDOWN))) / 3600
        saved = db.execute("SELECT COUNT(*) AS n FROM group_messages").fetchone()["n"]
        await event.respond(
            f"Settings\nDM auto-reply: {enabled}\n"
            f"DM cooldown: {cooldown:g} hours\n"
            f"Groups scanned: {db.execute('SELECT COUNT(*) FROM groups_list').fetchone()[0]}\n"
            f"Group messages saved: {saved}"
        )
    elif command == "groupset":
        try:
            group_id_text, message = argument.split(maxsplit=1)
            group_id = int(group_id_text)
            if len(message) > 4000:
                raise ValueError
            exists = db.execute(
                "SELECT 1 FROM groups_list WHERE group_id = ?", (group_id,)
            ).fetchone()
            if not exists:
                await event.respond("Unknown group ID. Run .groups and use an ID from that list.")
                return
            db.execute(
                """INSERT INTO group_messages(group_id, message, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                message = excluded.message, updated_at = excluded.updated_at""",
                (group_id, message, time.time()),
            )
            db.commit()
            await event.respond(f"Saved the message for group {group_id}. Nothing was sent.")
        except (ValueError, TypeError):
            await event.respond("Usage: .groupset <group_id> <message>")
    elif command == "groupview":
        rows = db.execute(
            """SELECT g.group_id, g.title, m.message FROM group_messages m
            JOIN groups_list g ON g.group_id = m.group_id ORDER BY g.title COLLATE NOCASE"""
        ).fetchall()
        if not rows:
            await event.respond("No group messages saved. Use .groupset <group_id> <message>.")
        else:
            parts = [f"{r['title']} (ID: {r['group_id']})\n{r['message']}" for r in rows]
            await event.respond("Saved group messages:\n\n" + "\n\n".join(parts))
    elif command == "groupclear":
        try:
            group_id = int(argument)
            cursor = db.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
            db.commit()
            await event.respond("Saved group message deleted." if cursor.rowcount else "No saved message for that group.")
        except ValueError:
            await event.respond("Usage: .groupclear <group_id>")
    elif command == "start":
        try:
            interval_text, message = argument.split(maxsplit=1)
            interval = float(interval_text)
            if interval < 3 or interval > 3600 or not message or len(message) > 4000:
                raise ValueError
        except ValueError:
            await event.respond("Usage: .start <seconds> <message> (3–3600 seconds; message up to 4000 characters).")
            return

        if BROADCAST_LOCK.locked():
            await event.respond("A group announcement is already running.")
            return

        rows = db.execute("SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE").fetchall()
        if not rows:
            await event.respond("No saved groups found. Run .groups or wait for the group scanner.")
            return

        async with BROADCAST_LOCK:
            await event.respond(f"Starting announcement to {len(rows)} saved groups. Delay: {interval:g} seconds. Groups where Telegram blocks posting will be skipped.")
            sent = 0
            failed = []
            for index, row in enumerate(rows):
                group_id = row["group_id"]
                title = row["title"] or str(group_id)
                try:
                    entity = await client.get_entity(group_id)
                    try:
                        await client.send_message(entity, message, link_preview=False)
                    except FloodWaitError as exc:
                        await asyncio.sleep(exc.seconds)
                        await client.send_message(entity, message, link_preview=False)
                    sent += 1
                except Exception as exc:
                    failed.append(f"{title} ({group_id}): {type(exc).__name__}")
                if index < len(rows) - 1:
                    await asyncio.sleep(interval)

            summary = f"Announcement finished.\nSuccessful: {sent}\nSkipped/failed: {len(failed)}\nTotal saved groups: {len(rows)}"
            if failed:
                summary += "\n\nCould not send to:\n" + "\n".join(f"• {item}" for item in failed[:30])
                if len(failed) > 30:
                    summary += f"\n…and {len(failed) - 30} more."
            await event.respond(summary)
    elif command == "dmstart":
        try:
            interval_text, message = argument.split(maxsplit=1)
            interval = float(interval_text)
            if interval < 10 or interval > 3600 or not message or len(message) > 4000:
                raise ValueError
        except ValueError:
            await event.respond("Usage: .dmstart <seconds> <message> (10–3600 seconds; message up to 4000 characters).")
            return

        if BROADCAST_LOCK.locked():
            await event.respond("Another broadcast is already running.")
            return

        me = await client.get_me()
        recipients = []
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if not getattr(entity, "id", None) or entity.id == me.id:
                continue
            if entity.__class__.__name__ != "User":
                continue
            if getattr(entity, "bot", False) or getattr(entity, "deleted", False):
                continue
            try:
                # Include only people with at least one incoming message in the chat history.
                incoming = await client.get_messages(entity, limit=1, from_user=entity)
                if incoming:
                    recipients.append((entity, getattr(entity, "first_name", None) or str(entity.id)))
            except Exception as exc:
                print(f"[DM SCAN] Skipped {entity.id}: {type(exc).__name__}")

        if not recipients:
            await event.respond("No eligible private chats found with an incoming message from the other person.")
            return

        async with BROADCAST_LOCK:
            await event.respond(
                f"Starting DM announcement for {len(recipients)} people who have previously messaged you. "
                f"Delay: {interval:g} seconds. Telegram privacy/restriction errors will be skipped."
            )
            sent = 0
            failed = []
            for index, (entity, display_name) in enumerate(recipients):
                try:
                    await client.send_message(entity, message, link_preview=False)
                    sent += 1
                except FloodWaitError as exc:
                    # Respect Telegram's requested wait; do not retry aggressively.
                    await asyncio.sleep(exc.seconds)
                    try:
                        await client.send_message(entity, message, link_preview=False)
                        sent += 1
                    except Exception as retry_exc:
                        failed.append(f"{display_name} ({entity.id}): {type(retry_exc).__name__}")
                except Exception as exc:
                    failed.append(f"{display_name} ({entity.id}): {type(exc).__name__}")
                if index < len(recipients) - 1:
                    await asyncio.sleep(interval)

            summary = (
                f"DM announcement finished.\\nSuccessful: {sent}\\n"
                f"Skipped/failed: {len(failed)}\\nTotal eligible: {len(recipients)}"
            )
            if failed:
                summary += "\\n\\nCould not send to:\\n" + "\\n".join(f"• {item}" for item in failed[:30])
                if len(failed) > 30:
                    summary += f"\\n…and {len(failed) - 30} more."
            await event.respond(summary)
    elif command == "groupsend":
        try:
            group_id = int(argument)
        except ValueError:
            await event.respond("Usage: .groupsend <group_id>")
            return
        row = db.execute(
            "SELECT message FROM group_messages WHERE group_id = ?", (group_id,)
        ).fetchone()
        if not row:
            await event.respond("No saved message for that group. Set one with .groupset first.")
            return
        if time.time() - LAST_GROUP_SEND < GROUP_SEND_INTERVAL:
            await event.respond("Please wait before sending another group message.")
            return
        try:
            entity = await client.get_entity(group_id)
            me = await client.get_me()
            permissions = await client.get_permissions(entity, me)
            if not (getattr(permissions, "is_admin", False) or getattr(permissions, "is_creator", False)):
                await event.respond("I can only send the saved message in a group where your account is an admin.")
                return
            await client.send_message(entity, row["message"], link_preview=False)
            LAST_GROUP_SEND = time.time()
            await event.respond(f"Saved message sent to {getattr(entity, 'title', 'the selected group')}.")
        except Exception as exc:
            await event.respond(f"Could not send to that group: {type(exc).__name__}: {exc}")


@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def private_dm_autoreply(event):
    try:
        sender = await event.get_sender()
        if not sender or sender.id == OWNER_ID or getattr(sender, "bot", False) or get_setting("dm_enabled", "1") != "1":
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
    print(f"[STARTED] Logged in as {me.username or me.id}; owner ID: {OWNER_ID}")
    group_count = await scan_groups()
    print(f"[STARTUP] Found {group_count} groups.")
    try:
        await client.send_message(OWNER_ID, f"Userbot is online. Logged in as {me.username or me.id}.\nGroups scanned: {group_count}\nSend .help here to control it.")
    except Exception as exc:
        print(f"[OWNER NOTIFICATION ERROR] {type(exc).__name__}: {exc}")
    asyncio.create_task(scan_loop())
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        db.close()
