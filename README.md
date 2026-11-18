# RizzGuru Helper

RizzGuru Helper has a BotFather bot for the existing automated group welcome flow and a Telethon userbot with the following owner-only controls.

## Userbot commands (private chat)

- `.help` — command list
- `.start 3 <message>` — group announcement, only in groups where your account is admin/creator
- `.startdm 3 <message>` — DM announcement only to subscribers who explicitly opted in
- `.setreply <message>` — configure automatic DM reply
- `.groups` — list group names, IDs and account status
- `.getgc` — CSV export of group names, IDs, invite links and status

For DM announcements, users opt in by sending `SUBSCRIBE` and opt out by sending `STOP`.

## Setup

Install dependencies, configure `.env` with bot token and Telethon credentials, then start the respective service. Keep credentials and session files private.
