"""Application entry point for RizzGuruHelper's Telegram bot."""
import logging

from telegram import Update
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
)

from config import BOT_TOKEN
from database import init_db
from handlers.admin import testwelcome
from handlers.basic import help_command, start
from handlers.welcome import on_chat_member
from utils.errors import error_handler

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("rizzguruhelper")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Copy .env.example to .env and set your bot token."
        )

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("testwelcome", testwelcome))
    app.add_handler(
        ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER)
    )
    app.add_error_handler(error_handler)

    logger.info("RizzGuruHelper bot starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
