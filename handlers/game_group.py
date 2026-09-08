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
        return await callback.answer(i18n.get("not_in_game", settings.DEFAULT_LANGUAGE), show_alert=True)

    user = callback.from_user
    async with async_session_maker() as session:
        await get_or_create_user(session, user.id, user.username, user.first_name)

    success = room.add_player(user.id, user.first_name, user.username)
    if not success:
        return await callback.answer(i18n.get("already_in_game", room.lang), show_alert=True)

    try:
        await callback.message.edit_text(
            room.get_lobby_text(),
            reply_markup=room.get_lobby_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer(i18n.get("player_joined", room.lang, name=user.first_name, count=len(room.players), min=settings.MIN_PLAYERS))

@game_group_router.callback_query(F.data == "game_leave")
async def cb_game_leave(callback: CallbackQuery):
    room = game_manager.get_room(callback.message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer(i18n.get("not_in_game", settings.DEFAULT_LANGUAGE), show_alert=True)

    user = callback.from_user
    success = room.remove_player(user.id)
    if not success:
        return await callback.answer(i18n.get("not_in_game", room.lang), show_alert=True)

    try:
        await callback.message.edit_text(
            room.get_lobby_text(),
            reply_markup=room.get_lobby_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer(i18n.get("player_left", room.lang, name=user.first_name))

@game_group_router.callback_query(F.data == "game_start_early")
async def cb_game_start_early(callback: CallbackQuery):
    room = game_manager.get_room(callback.message.chat.id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer("No active lobby.", show_alert=True)

    if callback.from_user.id != room.creator_id:
        return await callback.answer("Only the game creator can force start!", show_alert=True)

    if len(room.players) < settings.MIN_PLAYERS:
        return await callback.answer(f"Need at least {settings.MIN_PLAYERS} players!", show_alert=True)

    await callback.answer("🚀 Starting game now!")
    await room.start_game(callback.bot)

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
