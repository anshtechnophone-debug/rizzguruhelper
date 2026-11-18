# RizzGuru Helper — Telethon userbot

## Owner commands (send privately to the logged-in account)

- `.help` — list commands
- `.start 3 <message>` — post an announcement to groups where your account is an admin/creator
- `.startdm 3 <message>` — send only to people who opted in by messaging `SUBSCRIBE`
- `.setreply <message>` — set the automatic DM reply
- `.groups` — list group names, IDs and admin/member status
- `.getgc` — create a CSV of group names, IDs, invite links and link availability

DM subscribers can send `STOP` to opt out. The userbot does not DM non-subscribers.

## Setup

Set `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `OWNER_ID` in `.env`. Start with `python -m userbot.main`.

Keep API credentials, session files and `.env` private. Never commit them.
