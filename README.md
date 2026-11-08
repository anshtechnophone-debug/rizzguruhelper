# RizzGuruHelper

A modular Telegram group bot built with Python and python-telegram-bot.

## Current features

- `/start` and `/help` commands.
- Detects members joining a group.
- Creates a personal invite link for each new member.
- Posts a welcome message with a Telegram share button.
- `/testwelcome` lets a group administrator test the welcome flow.
- Stores each member's personal invite link in SQLite.

## Requirements

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- The bot must be an administrator in each group where it should create invite links. Grant the permission to manage invite links.

## Setup

```bash
git clone https://github.com/anshtechnophone-debug/rizzguruhelper.git
cd rizzguruhelper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

Set `BOT_TOKEN` in `.env`. Never commit your real token or session credentials.

## Project structure

```text
.
├── bot.py
├── config.py
├── database.py
├── handlers/
│   ├── __init__.py
│   ├── admin.py
│   ├── basic.py
│   └── welcome.py
├── utils/
│   ├── __init__.py
│   └── errors.py
├── requirements.txt
├── .env.example
└── README.md
```

Handlers, database access, configuration, and shared utilities are separated so features can be extended without putting the whole bot in one file.
