"""Centralized Telegram application error logging."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("rizzguruhelper")


async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if context.error:
        logger.error(
            "Unhandled error while processing update %r",
            update if isinstance(update, Update) else None,
            exc_info=(
                type(context.error),
                context.error,
                context.error.__traceback__,
            ),
        )
