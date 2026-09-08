import asyncio
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from config import settings
from database.crud import get_or_create_group, get_or_create_user
from database.database import async_session_maker
from game.enums import GamePhase
from game.manager import game_manager
from locales.i18n import i18n

game_group_router = Router()

@game_group_router.message(Command("game", "oyun", "mafia"))
async def cmd_game(message: Message):
    if message.chat.type == "private":
        await message.answer("⚠️ You can only play Mafia in a group chat! Add me to your group.", parse_mode="HTML")
        return

    chat_id = message.chat.id
    existing_room = game_manager.get_room(chat_id)
    if existing_room and existing_room.phase != GamePhase.GAME_OVER:
        await message.answer("⚠️ A game is already active or in lobby in this chat!", parse_mode="HTML")
        return

    async with async_session_maker() as session:
        group = await get_or_create_group(session, chat_id, message.chat.title or "Group")
        await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        lang = group.language

    # Create room
    room = game_manager.create_room(
        chat_id=chat_id,
        creator_id=message.from_user.id,
        creator_name=message.from_user.first_name,
        lang=lang
    )

    msg = await message.answer(
        room.get_lobby_text(),
        reply_markup=room.get_lobby_markup(),
        parse_mode="HTML"
    )
    room.lobby_message_id = msg.message_id
    room.timer_task = asyncio.create_task(room.start_countdown(message.bot))

@game_group_router.callback_query(F.data == "game_join")
async def cb_game_join(callback: CallbackQuery):
    room = game_manager.get_room(callback.message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer("⚠️ Hozirda faol ro'yxatdan o'tish mavjud emas.", show_alert=True)

    user = callback.from_user
    if user.id in room.players:
        return await callback.answer("⚠️ Siz allaqachon o'yindasiz!", show_alert=True)

    # Check if bot can message player in PM
    try:
        await callback.bot.send_chat_action(user.id, "typing")
    except Exception:
        # Player hasn't opened bot PM yet
        return await callback.answer(
            f"⚠️ Bot sizga maxfiy rolingizni yuborishi uchun avval botga kiring va START bosing:\n@{settings.BOT_USERNAME}",
            show_alert=True
        )

    async with async_session_maker() as session:
        await get_or_create_user(session, user.id, user.username, user.first_name)

    success = room.add_player(user.id, user.first_name, user.username)
    if not success:
        return await callback.answer("⚠️ O'yinga qo'shilish imkoni bo'lmadi (xona to'lgan).", show_alert=True)

    try:
        await callback.message.edit_text(
            room.get_lobby_text(),
            reply_markup=room.get_lobby_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer(f"✅ O'yinga qo'shildingiz! ({len(room.players)}/{settings.MIN_PLAYERS})")

@game_group_router.callback_query(F.data == "game_leave")
async def cb_game_leave(callback: CallbackQuery):
    room = game_manager.get_room(callback.message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer("⚠️ Faol o'yin xonasi mavjud emas.", show_alert=True)

    user = callback.from_user
    if user.id not in room.players:
        return await callback.answer("⚠️ Siz bu o'yinda emassiz!", show_alert=True)

    success = room.remove_player(user.id)
    if not success:
        return await callback.answer("⚠️ O'yindan chiqishda xatolik yuz berdi.", show_alert=True)

    # If creator left, transfer to someone else
    if user.id == room.creator_id and room.players:
        next_id = next(iter(room.players.keys()))
        room.creator_id = next_id
        room.creator_name = room.players[next_id].name

    # If no players left, cancel room
    if not room.players:
        game_manager.remove_room(room.chat_id)
        try:
            await callback.message.edit_text(
                "🛑 <b>Barcha o'yinchilar chiqib ketganligi sababli o'yin bekor qilindi.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return await callback.answer("🚪 Siz o'yindan chiqdingiz.")

    try:
        await callback.message.edit_text(
            room.get_lobby_text(),
            reply_markup=room.get_lobby_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("🚪 Siz o'yindan chiqdingiz.")

@game_group_router.callback_query(F.data == "game_start_early")
async def cb_game_start_early(callback: CallbackQuery):
    room = game_manager.get_room(callback.message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer("⚠️ Faol o'yin xonasi mavjud emas.", show_alert=True)

    user_id = callback.from_user.id
    is_allowed = (user_id in room.players) or (user_id == room.creator_id) or (user_id in settings.ADMIN_IDS)
    if not is_allowed:
        return await callback.answer("⚠️ O'yinni boshlash uchun avval o'yinga qo'shiling!", show_alert=True)

    if len(room.players) < settings.MIN_PLAYERS:
        return await callback.answer(
            f"⚠️ Kamida {settings.MIN_PLAYERS} ta o'yinchi kerak! (Hozir: {len(room.players)}/{settings.MIN_PLAYERS})",
            show_alert=True
        )

    await callback.answer("🚀 O'yin boshlanmoqda...")
    try:
        await room.start_game(callback.bot)
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        await callback.message.answer(f"⚠️ O'yinni boshlashda xatolik yuz berdi: {e}")

@game_group_router.message(Command("startgame", "boshlash"))
async def cmd_start_game_group(message: Message):
    if message.chat.type == "private":
        return
    room = game_manager.get_room(message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return

    user_id = message.from_user.id
    is_allowed = (user_id in room.players) or (user_id == room.creator_id) or (user_id in settings.ADMIN_IDS)
    if not is_allowed:
        await message.reply("⚠️ O'yinni boshlash uchun avval o'yinga qo'shiling!")
        return

    if len(room.players) < settings.MIN_PLAYERS:
        await message.reply(f"⚠️ Kamida {settings.MIN_PLAYERS} ta o'yinchi kerak! (Hozir: {len(room.players)}/{settings.MIN_PLAYERS})")
        return

    await message.reply("🚀 O'yin boshlanmoqda...")
    try:
        await room.start_game(message.bot)
    except Exception as e:
        logger.error(f"Error starting game via command: {e}")

@game_group_router.callback_query(F.data == "game_extend_time")
async def cb_game_extend_time(callback: CallbackQuery):
    room = game_manager.get_room(callback.message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer(i18n.get("not_in_game", settings.DEFAULT_LANGUAGE), show_alert=True)

    if room.seconds_left >= 300:
        return await callback.answer("⚠️ Maksimal vaqt (5 daqiqa) ga yetdi!", show_alert=True)

    new_time = room.extend_lobby_time(30)
    try:
        await callback.message.edit_text(
            room.get_lobby_text(),
            reply_markup=room.get_lobby_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer(f"⏳ +30s ({new_time}s)", show_alert=False)

@game_group_router.message(Command("extend", "vaqt", "time", "plus30"))
async def cmd_extend_time(message: Message):
    room = game_manager.get_room(message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return

    if room.seconds_left >= 300:
        await message.reply("⚠️ Maksimal vaqt chegarasiga (5 daqiqa) yetilgan.", parse_mode="HTML")
        return

    new_time = room.extend_lobby_time(30)
    if room.lobby_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=room.chat_id,
                message_id=room.lobby_message_id,
                text=room.get_lobby_text(),
                reply_markup=room.get_lobby_markup(),
                parse_mode="HTML"
            )
        except Exception:
            pass
    await message.reply(i18n.get("time_extended", room.lang, seconds=new_time), parse_mode="HTML")

@game_group_router.callback_query(F.data.startswith("check_role_"))
async def cb_check_role(callback: CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    room = game_manager.get_room(chat_id)
    if not room or room.phase in [GamePhase.LOBBY, GamePhase.GAME_OVER]:
        return await callback.answer("O'yin hozir faol emas.", show_alert=True)

    player = room.players.get(callback.from_user.id)
    if not player:
        return await callback.answer("Siz bu o'yinda ishtirok etmayapsiz!", show_alert=True)

    role_title = i18n.get(f"roles.{player.role.value}", room.lang)
    desc = i18n.get(f"role_desc.{player.role.value}", room.lang)
    status = "Tirik" if player.is_alive else "Halok bo'lgan"
    await callback.answer(
        f"🎭 Sizning rolingiz: {role_title} ({status})\n\n{desc}",
        show_alert=True
    )

@game_group_router.message(Command("join", "qoshilish", "qosul"))
async def cmd_join_group(message: Message):
    room = game_manager.get_room(message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return
    user = message.from_user
    async with async_session_maker() as session:
        await get_or_create_user(session, user.id, user.username, user.first_name)
    success = room.add_player(user.id, user.first_name, user.username)
    if success and room.lobby_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=room.chat_id,
                message_id=room.lobby_message_id,
                text=room.get_lobby_text(),
                reply_markup=room.get_lobby_markup(),
                parse_mode="HTML"
            )
        except Exception:
            pass

@game_group_router.message(Command("stop"))
async def cmd_stop(message: Message):
    room = game_manager.get_room(message.chat.id)
    if not room or room.phase == GamePhase.GAME_OVER:
        await message.answer("⚠️ No active game in this chat.", parse_mode="HTML")
        return

    # Check creator or admin
    if message.from_user.id != room.creator_id and message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("⚠️ Only the game creator or an admin can stop the game!", parse_mode="HTML")
        return

    game_manager.remove_room(message.chat.id)
    await message.answer("🛑 <b>Game was forcefully stopped!</b>", parse_mode="HTML")

@game_group_router.callback_query(F.data.startswith("vote_"))
async def cb_day_vote(callback: CallbackQuery):
    parts = callback.data.split("_")
    chat_id = int(parts[1])
    target_id = int(parts[2])

    room = game_manager.get_room(chat_id)
    if not room or room.phase != GamePhase.VOTING:
        return await callback.answer("Voting is not currently active!", show_alert=True)

    voter_id = callback.from_user.id
    success = await room.cast_day_vote(voter_id, target_id, callback.bot)
    if success:
        target_name = room.players[target_id].name if target_id in room.players else "Target"
        await callback.answer(f"✅ Voted for {target_name}!")
    else:
        await callback.answer("Could not cast vote (are you dead or not playing?)", show_alert=True)

@game_group_router.callback_query(F.data.startswith("skip_last_words_"))
async def cb_skip_last_words(callback: CallbackQuery):
    parts = callback.data.split("_")
    # skip_last_words_{chat_id}_{lynched_id}
    chat_id = int(parts[3])
    lynched_id = int(parts[4])

    room = game_manager.get_room(chat_id)
    if not room or room.phase != GamePhase.LAST_WORDS:
        return await callback.answer("Hozirda so'nggi so'z bosqichi emas.", show_alert=True)

    if callback.from_user.id != lynched_id:
        return await callback.answer("Faqat hukm qilingan o'yinchi vaqtni o'tkazib yuborishi mumkin!", show_alert=True)

    if room.last_words_event and not room.last_words_event.is_set():
        room.last_words_event.set()
        await callback.answer("⚰️ Tayyor deb belgilandi!", show_alert=False)
