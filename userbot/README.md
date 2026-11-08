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
- .groups — list groups already joined by your account
- .replyon / .replyoff — toggle private-message auto-replies
- .replyset <text> — set the reply text
- .cooldown 24 — set cooldown in hours (1–720)

The scanner only records groups your account already belongs to. It does not
join arbitrary links or send unsolicited campaigns. Keep API credentials,
the session file, and .env private. Never commit them to Git.
