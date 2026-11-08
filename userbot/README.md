# Telethon personal-account userbot

This is separate from the BotFather welcome bot. It logs in to the Telegram
account you authorize through Telethon.

## Setup

1. Copy .env.example to .env.
2. Set TELEGRAM_API_ID and TELEGRAM_API_HASH from https://my.telegram.org.
3. Install dependencies with pip install -r requirements.txt.
4. Start with python -m userbot.main and complete the Telegram login prompt.

## Commands (send from Saved Messages)

- .help — command list
- .groups — list groups already joined by your account (includes IDs)
- .replyon / .replyoff — toggle private-message auto-replies
- .replyset <text> — set the automatic DM reply
- .dmview — preview the current DM reply
- .cooldown 24 — set DM cooldown in hours (1–720)
- .status — show current settings
- .groupset <group_id> <text> — save or replace a message for one group; this does not send it
- .groupview — view saved group messages
- .groupsend <group_id> — explicitly send the saved message to that one group
- .groupclear <group_id> — remove a group's saved message

Group sending is manual, one selected group at a time, limited to groups where
your account is an administrator. A 30-second interval is enforced between
group sends. There is no group-wide broadcast or automatic campaign feature.

The scanner only records groups your account already belongs to. It does not
join arbitrary links or send unsolicited campaigns. Keep API credentials,
the session file, and .env private. Never commit them to Git.
