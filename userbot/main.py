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
CAMPAIGN_TASK = None
CAMPAIGN_DECISION = None
CAMPAIGN_STOP_REQUESTED = False
CAMPAIGN_NEXT_ROUND = False


async def run_campaign(chat_id, delay, message, eligible):
    global CAMPAIGN_DECISION, CAMPAIGN_STOP_REQUESTED, CAMPAIGN_NEXT_ROUND
    sent_total = failed_total = rounds = 0
    try:
        while True:
            rounds += 1
            sent = failed = 0
            await client.send_message(
                chat_id,
                f"Starting announcement round {rounds} across {len(eligible)} eligible groups."
            )
            for index, (entity, title) in enumerate(eligible):
                if CAMPAIGN_STOP_REQUESTED:
                    break
                try:
                    await client.send_message(entity, message, link_preview=False)
                    sent += 1
                except FloodWaitError as exc:
                    # Respect Telegram's requested wait; do not retry-loop.
                    await asyncio.sleep(exc.seconds)
                    if CAMPAIGN_STOP_REQUESTED:
                        break
                    try:
                        await client.send_message(entity, message, link_preview=False)
                        sent += 1
                    except Exception:
                        failed += 1
                except Exception:
                    failed += 1
                if index < len(eligible) - 1 and not CAMPAIGN_STOP_REQUESTED:
                    await asyncio.sleep(delay)

            sent_total += sent
            failed_total += failed
            if CAMPAIGN_STOP_REQUESTED:
                break

            await client.send_message(
                chat_id,
                f"Round {rounds} complete. Sent: {sent}; failed: {failed}. "
                "Waiting 2 minutes before asking for confirmation."
            )
            CAMPAIGN_DECISION = asyncio.Event()
            CAMPAIGN_NEXT_ROUND = False
            try:
                await asyncio.wait_for(CAMPAIGN_DECISION.wait(), timeout=120)
            except asyncio.TimeoutError:
                pass

            if CAMPAIGN_STOP_REQUESTED:
                break
            if not CAMPAIGN_NEXT_ROUND:
                await client.send_message(
                    chat_id,
                    "Paused: no confirmation received. Send .continue to start another round, "
                    "or .stop to end the announcement."
                )
                CAMPAIGN_DECISION = asyncio.Event()
                await CAMPAIGN_DECISION.wait()
                if CAMPAIGN_STOP_REQUESTED:
                    break
                if not CAMPAIGN_NEXT_ROUND:
                    continue
            CAMPAIGN_DECISION = None

        await client.send_message(
            chat_id,
            f"Announcement stopped. Rounds completed: {rounds}; "
            f"total sent: {sent_total}; total failed: {failed_total}."
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        await client.send_message(
            chat_id, f"Announcement stopped due to an error: {type(exc).__name__}: {exc}"
        )
    finally:
        CAMPAIGN_DECISION = None
        CAMPAIGN_STOP_REQUESTED = False
        CAMPAIGN_NEXT_ROUND = False


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
    ".start 3 <message> — send one announcement round\n"
    ".continue — confirm the next round (after the 2-minute wait)\n"
    ".stop — stop the active announcement\n"
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


@client.on(events.NewMessage(incoming=True, pattern=r"^\.(help|groups|setreply|getgc|start)(?:\s+([\s\S]*))?$"))
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
        # Acknowledge immediately so the owner knows the command was received.
        progress = await event.respond("Checking your saved groups…")
        rows = db.execute(
            "SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE"
        ).fetchall()

        if not rows:
            await progress.edit("No saved groups found yet. Refreshing the group list…")
            try:
                await scan_groups()
                rows = db.execute(
                    "SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE"
                ).fetchall()
            except Exception as exc:
                await progress.edit(f"Could not scan groups: {type(exc).__name__}: {exc}")
                return

        if not rows:
            await progress.edit("No groups were found in this account.")
            return

        try:
            me = await client.get_me()
        except Exception as exc:
            await progress.edit(f"Could not identify the logged-in account: {type(exc).__name__}: {exc}")
            return

        batch = []
        sent_count = 0
        total = len(rows)
        for index, row in enumerate(rows, 1):
            title = row["title"] or str(row["group_id"])
            try:
                entity = await client.get_entity(row["group_id"])
                perms = await client.get_permissions(entity, me)
                status = (
                    "admin" if (
                        getattr(perms, "is_admin", False)
                        or getattr(perms, "is_creator", False)
                    ) else "member"
                )
            except Exception as exc:
                status = f"unavailable ({type(exc).__name__})"

            batch.append(f"• {title} | {row['group_id']} | {status}")
            if len(batch) >= 25 or index == total:
                header = f"Groups status ({index - len(batch) + 1}–{index} of {total}):\n"
                try:
                    await event.respond(header + "\n".join(batch))
                    sent_count += len(batch)
                except Exception as exc:
                    await progress.edit(
                        f"Checked {index}/{total} groups, but couldn't send the results: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return
                batch.clear()
                if index < total:
                    await progress.edit(f"Checked {index}/{total} groups…")

        await progress.edit(f"Finished checking {sent_count} groups.")
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

    global CAMPAIGN_TASK, CAMPAIGN_DECISION, CAMPAIGN_STOP_REQUESTED, CAMPAIGN_NEXT_ROUND

    if command == "stop":
        if not CAMPAIGN_TASK or CAMPAIGN_TASK.done():
            await event.respond("No announcement is currently running.")
            return
        CAMPAIGN_STOP_REQUESTED = True
        if CAMPAIGN_DECISION:
            CAMPAIGN_DECISION.set()
        await event.respond("Stop requested. The announcement will stop after any current Telegram wait finishes.")
        return

    if command == "continue":
        if not CAMPAIGN_TASK or CAMPAIGN_TASK.done():
            await event.respond("There is no paused announcement to continue.")
            return
        if CAMPAIGN_STOP_REQUESTED:
            await event.respond("The announcement is already stopping.")
            return
        if not CAMPAIGN_DECISION:
            await event.respond("The announcement is still sending or the 2-minute wait has not finished.")
            return
        CAMPAIGN_NEXT_ROUND = True
        CAMPAIGN_DECISION.set()
        await event.respond("Confirmed. The next announcement round will start.")
        return

    if command == "start":
        parsed = parse_campaign(argument)
        if not parsed:
            await event.respond(f"Usage: .{command} <seconds> <message> (3–3600 seconds; message up to 4000 characters).")
            return
        if CAMPAIGN_TASK and not CAMPAIGN_TASK.done():
            await event.respond("An announcement is already running. Use .stop to end it.")
            return

        delay, message = parsed
        rows = db.execute("SELECT group_id, title FROM groups_list ORDER BY title COLLATE NOCASE").fetchall()
        eligible = []
        me = await client.get_me()
        for row in rows:
            try:
                entity = await client.get_entity(row["group_id"])
                permissions = await client.get_permissions(entity, me)
                if getattr(permissions, "is_admin", False) or getattr(permissions, "is_creator", False):
                    eligible.append((entity, row["title"] or str(row["group_id"])))
            except Exception:
                continue
        if not eligible:
            await event.respond("No groups where your account has admin/creator permissions.")
            return

        CAMPAIGN_STOP_REQUESTED = False
        CAMPAIGN_NEXT_ROUND = False
        CAMPAIGN_DECISION = None
        CAMPAIGN_TASK = asyncio.create_task(
            run_campaign(event.chat_id, delay, message, eligible)
        )
        await event.respond(
            f"Announcement started for {len(eligible)} eligible groups, with {delay:g}s "
            "between groups. Each round is sent once. After a round, it waits 2 minutes; "
            "then use .continue to confirm another round or .stop to end it."
        )
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
