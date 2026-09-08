import asyncio
import html
import random
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from game.enums import GamePhase, Role, Team
from game.manager import game_manager
from locales.i18n import i18n

game_private_router = Router()

@game_private_router.callback_query(F.data.startswith("set_will_"))
async def cb_set_will(callback: CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    room = game_manager.get_room(chat_id)
    lang = room.lang if room else "uz"
    await callback.answer()
    await callback.message.answer(i18n.get("will_prompt", lang), parse_mode="HTML")

@game_private_router.message(F.chat.type == "private", Command("will", "vasiyat"))
async def cmd_will(message: Message, command: CommandObject):
    user_id = message.from_user.id
    room = game_manager.find_user_room(user_id)
    if not room or room.phase in [GamePhase.LOBBY, GamePhase.GAME_OVER]:
        return await message.reply("⚠️ Hozirda faol o'yinda ishtirok etmayapsiz!", parse_mode="HTML")

    player = room.players.get(user_id)
    if not player or not player.is_alive:
        return await message.reply("⚠️ Siz tirik o'yinchi emassiz!", parse_mode="HTML")

    if not command.args or not command.args.strip():
        return await message.reply(i18n.get("will_prompt", room.lang), parse_mode="HTML")

    will_text = command.args.strip()[:250]
    player.last_will = will_text
    clean_will = html.escape(will_text)
    await message.reply(i18n.get("will_saved", room.lang, will=clean_will), parse_mode="HTML")

@game_private_router.callback_query(F.data.startswith("act_"))
async def cb_night_action(callback: CallbackQuery):
    parts = callback.data.split("_")
    # act_{chat_id}_{role}_{target_id}
    chat_id = int(parts[1])
    role_str = parts[2]
    target_id = int(parts[3])

    room = game_manager.get_room(chat_id)
    if not room or room.phase != GamePhase.NIGHT:
        return await callback.answer("The night phase has already ended!", show_alert=True)

    user_id = callback.from_user.id
    if user_id not in room.players or not room.players[user_id].is_alive:
        return await callback.answer("You are not an active player in this game.", show_alert=True)

    if target_id not in room.players or not room.players[target_id].is_alive:
        return await callback.answer("Target is not valid or already dead.", show_alert=True)

    target_player = room.players[target_id]
    target_name = html.escape(target_player.name)

    if role_str in [Role.DON.value, Role.MAFIA.value]:
        room.mafia_votes[user_id] = target_id
        await callback.message.edit_text(
            i18n.get("action_recorded", room.lang, target=target_name),
            parse_mode="HTML"
        )
        await callback.answer()
        await room.announce_night_action(callback.bot, role_str)

    elif role_str == Role.DOCTOR.value:
        room.doctor_target = target_id
        await callback.message.edit_text(
            i18n.get("action_recorded", room.lang, target=target_name),
            parse_mode="HTML"
        )
        await callback.answer()
        await room.announce_night_action(callback.bot, role_str)

    elif role_str == Role.DETECTIVE.value:
        room.detective_target = target_id
        # Secret detective report (check Fog weather event)
        if room.current_event == "event_fog" and random.random() < 0.25:
            res_msg = i18n.get("fog_investigation_obscured", room.lang, target=target_name)
        elif getattr(target_player, "has_fake_docs", False):
            target_player.has_fake_docs = False
            from database.database import async_session_maker
            from services.economy_service import consume_fake_documents
            try:
                async with async_session_maker() as session:
                    await consume_fake_documents(session, target_player.user_id)
            except Exception:
                pass
            res_msg = i18n.get("detective_result_fakedocs", room.lang, target=target_name)
        else:
            is_mafia = (target_player.team == Team.MAFIA and not target_player.protected_by_lawyer)
            if is_mafia:
                res_msg = i18n.get("detective_result_mafia", room.lang, target=target_name)
            else:
                res_msg = i18n.get("detective_result_innocent", room.lang, target=target_name)

        await callback.message.edit_text(res_msg, parse_mode="HTML")
        await callback.answer()
        await room.announce_night_action(callback.bot, role_str)

    elif role_str == Role.MANIAC.value:
        room.maniac_target = target_id
        await callback.message.edit_text(
            i18n.get("action_recorded", room.lang, target=target_name),
            parse_mode="HTML"
        )
        await callback.answer()
        await room.announce_night_action(callback.bot, role_str)

    elif role_str == Role.MISTRESS.value:
        room.mistress_target = target_id
        await callback.message.edit_text(
            i18n.get("action_recorded", room.lang, target=target_name),
            parse_mode="HTML"
        )
        await callback.answer()
        await room.announce_night_action(callback.bot, role_str)

    elif role_str == Role.SNIPER.value:
        room.sniper_target = target_id
        await callback.message.edit_text(
            i18n.get("action_recorded", room.lang, target=target_name),
            parse_mode="HTML"
        )
        await callback.answer()
        await room.announce_night_action(callback.bot, role_str)

    # Check if all night actions are collected to finish night early!
    if room.are_all_night_actions_done():
        if room.timer_task and not room.timer_task.done():
            room.timer_task.cancel()
        asyncio.create_task(room.resolve_night(callback.bot))

@game_private_router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def pm_mafia_chat_relay(message: Message):
    """Allow living Mafia and Don to secretly chat with each other during the night phase."""
    user_id = message.from_user.id
    for room in list(game_manager.rooms.values()):
        if room.phase == GamePhase.NIGHT and user_id in room.players:
            player = room.players[user_id]
            if player.is_alive and player.role in [Role.DON, Role.MAFIA]:
                text = message.text or message.caption or "[Ovozli xabar / Media]"
                relayed = await room.broadcast_mafia_chat(
                    bot=message.bot,
                    sender_id=user_id,
                    sender_name=message.from_user.first_name,
                    text=text
                )
                if relayed:
                    await message.reply("🩸 <i>Xabaringiz Mafiya a'zolariga yetkazildi.</i>", parse_mode="HTML")
                return
