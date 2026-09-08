import logging
from typing import List
from aiogram import Bot
from aiogram.types import ChatPermissions

logger = logging.getLogger(__name__)

# Permissions for day discussion: allowed to talk
DAY_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=False,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False
)

# Permissions for night silence: no talking
NIGHT_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False
)

# Permissions for dead/eliminated players: muted
DEAD_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_other_messages=False
)

async def mute_chat_night(bot: Bot, chat_id: int):
    """Mute the entire group during the night cycle."""
    try:
        await bot.set_chat_permissions(chat_id=chat_id, permissions=NIGHT_PERMISSIONS)
    except Exception as e:
        logger.warning(f"Failed to mute chat {chat_id} for night: {e}")

async def unmute_chat_day(bot: Bot, chat_id: int):
    """Unmute the group when morning breaks."""
    try:
        await bot.set_chat_permissions(chat_id=chat_id, permissions=DAY_PERMISSIONS)
    except Exception as e:
        logger.warning(f"Failed to unmute chat {chat_id} for day: {e}")

async def mute_dead_player(bot: Bot, chat_id: int, user_id: int):
    """Mute a dead player so they cannot ghost or influence living players."""
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=DEAD_PERMISSIONS
        )
    except Exception as e:
        logger.warning(f"Failed to restrict dead user {user_id} in {chat_id}: {e}")

async def restore_players(bot: Bot, chat_id: int, user_ids: List[int]):
    """Restore default permissions for all players after game ends."""
    await unmute_chat_day(bot, chat_id)
    for u_id in user_ids:
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=u_id,
                permissions=DAY_PERMISSIONS
            )
        except Exception:
            pass
