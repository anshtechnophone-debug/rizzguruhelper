"""Administrator-only test commands."""
import logging

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from handlers.welcome import welcome_member

logger = logging.getLogger(__name__)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or chat.type == "private":
        return False

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        logger.exception("Admin check failed")
        return False


async def testwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(
                "Only group administrators can use this command."
            )
        return

    if update.effective_chat and update.effective_user:
        await welcome_member(
            context.bot,
            update.effective_chat,
            update.effective_user,
        )
