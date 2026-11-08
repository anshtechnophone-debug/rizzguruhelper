"""Public start and help commands."""
from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "👋 Member Gate Bot is running.\n\n"
            "Add me as a group administrator with permission to manage invite links.\n\n"
            "New members will receive a personal invite-sharing button."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "🤖 Member Gate Bot\n\n"
            "/start - Start the bot\n"
            "/help - Show help\n"
            "/testwelcome - Test the welcome message (group admins only)\n\n"
            "Every new member receives their own invitation link."
        )
