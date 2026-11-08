"""New-member detection and personal invite-sharing welcome."""
import logging
from urllib.parse import urlencode

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from database import save_link

logger = logging.getLogger(__name__)


def is_member(member) -> bool:
    status = member.status
    if status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ):
        return True
    if status == ChatMemberStatus.RESTRICTED:
        return bool(getattr(member, "is_member", False))
    return False


async def create_personal_link(bot, chat_id: int, user: User) -> str:
    invite = await bot.create_chat_invite_link(
        chat_id=chat_id,
        name=f"Member-{user.id}",
        creates_join_request=False,
    )
    save_link(chat_id, user.id, invite.invite_link)
    return invite.invite_link


async def welcome_member(bot, chat, user: User) -> None:
    if user.is_bot:
        return

    try:
        personal_link = await create_personal_link(bot, chat.id, user)
        share_url = "https://t.me/share/url?" + urlencode({
            "url": personal_link,
            "text": f"Join our Telegram group: {chat.title}",
        })
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📤 Share My Invite Link", url=share_url)
        ]])

        await bot.send_message(
            chat_id=chat.id,
            text=(
                f"👋 Welcome, {user.mention_html()}!\n\n"
                "Invite your friends to our group using your personal "
                "invitation link.\n\n"
                "👇 Tap below to choose a DM or group to share it in."
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Could not create welcome message for user %s", user.id)


async def on_chat_member(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    event = update.chat_member
    if not event:
        return

    if is_member(event.old_chat_member) or not is_member(event.new_chat_member):
        return

    await welcome_member(context.bot, event.chat, event.new_chat_member.user)
