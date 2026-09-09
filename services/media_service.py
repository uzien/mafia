import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

GAME_ANIMATIONS = {
    # 🎬 Game start / Noir city
    "game_start": "https://media.giphy.com/media/l0MYEqEzwMWFCg8rm/giphy.gif",
    
    # 🌚 Night fell / Moonlight / Dark street
    "night_start": "https://media.giphy.com/media/3o7TKMt1VVNkHV2PaE/giphy.gif",
    
    # 🌅 Peaceful morning / Sunrise
    "morning_peaceful": "https://media.giphy.com/media/l4pT0NtPSMV3pw65O/giphy.gif",
    
    # 🚨 Crime scene / Red sirens / Murder discovered
    "morning_murder": "https://media.giphy.com/media/3o7TKTDnUxE0g2fSE8/giphy.gif",
    
    # ⚖️ Court / Gavel / Trial by town
    "court_trial": "https://media.giphy.com/media/3oKIPbNb1vWd0btuIE/giphy.gif",
    
    # ⚰️ Execution / Lynch
    "execution": "https://media.giphy.com/media/l2YWm9m1kK89bY7gQ/giphy.gif",
    
    # 🏆 Victory: Town (Sunrise / Celebration)
    "victory_town": "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif",
    
    # 🩸 Victory: Mafia (The Godfather / Cigarette / Dark city)
    "victory_mafia": "https://media.giphy.com/media/13pbEUgBpPIeaY/giphy.gif",
    
    # 🔪 Victory: Maniac (Solo blade / Shadows)
    "victory_maniac": "https://media.giphy.com/media/10mBc2m6rWJ3fa/giphy.gif",
    
    # 🃏 Victory: Jester (Laughing Joker)
    "victory_jester": "https://media.giphy.com/media/tMyCJmeXHBetq/giphy.gif"
}

async def send_game_animation(
    bot: Bot,
    chat_id: int,
    animation_key: str,
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> Optional[Message]:
    anim_url = GAME_ANIMATIONS.get(animation_key)
    
    if anim_url:
        try:
            return await bot.send_animation(
                chat_id=chat_id,
                animation=anim_url,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send animation '{animation_key}' to {chat_id}: {e}. Falling back to text.")

    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send fallback message to {chat_id}: {e}")
        return None
