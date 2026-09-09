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

@game_private_router.callback_query(F.data.startswith("creator_start_"))
async def cb_creator_start(callback: CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    room = game_manager.get_room(chat_id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer("⚠️ Bu o'yin allaqachon boshlangan yoki yakunlangan.", show_alert=True)

    if callback.from_user.id != room.creator_id:
        return await callback.answer("⚠️ Faqat o'yin yaratuvchisi o'yinni boshlashi mumkin!", show_alert=True)

    from config import settings
    if len(room.players) < settings.MIN_PLAYERS:
        return await callback.answer(
            f"⚠️ Kamida {settings.MIN_PLAYERS} ta o'yinchi kerak! (Hozir: {len(room.players)}/{settings.MIN_PLAYERS})",
            show_alert=True
        )

    await callback.answer("🚀 O'yin boshlanmoqda...")
    try:
        await room.start_game(callback.bot)
    except Exception as e:
        await callback.message.answer(f"⚠️ O'yinni boshlashda xatolik: {e}")

@game_private_router.callback_query(F.data.startswith("creator_extend_"))
async def cb_creator_extend(callback: CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    room = game_manager.get_room(chat_id)
    if not room or room.phase != GamePhase.LOBBY:
        return await callback.answer("⚠️ Faol o'yin xonasi topilmadi.", show_alert=True)

    if callback.from_user.id != room.creator_id:
        return await callback.answer("⚠️ Faqat o'yin yaratuvchisi vaqtni uzaytira oladi!", show_alert=True)

    if room.seconds_left >= 300:
        return await callback.answer("⚠️ Maksimal vaqt chegarasiga (5 daqiqa) yetildi!", show_alert=True)

    new_time = room.extend_lobby_time(30)
    await room.sync_lobby_messages(callback.bot)
    await callback.answer(f"⏳ +30s qo'shildi ({new_time}s)")

@game_private_router.callback_query(F.data.startswith("creator_cancel_"))
async def cb_creator_cancel(callback: CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    room = game_manager.get_room(chat_id)
    if not room or room.phase == GamePhase.GAME_OVER:
        return await callback.answer("⚠️ Faol o'yin mavjud emas.", show_alert=True)

    if callback.from_user.id != room.creator_id:
        return await callback.answer("⚠️ Faqat o'yin yaratuvchisi o'yinni bekor qila oladi!", show_alert=True)

    await game_manager.stop_and_remove_room(chat_id, callback.bot)
    try:
        await callback.message.edit_text("🛑 <b>O'yin bekor qilindi.</b>", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("🛑 O'yin bekor qilindi!")

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

@game_private_router.callback_query(F.data.startswith("skip_letter_"))
async def cb_skip_letter(callback: CallbackQuery):
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    user_id = int(parts[3])
    room = game_manager.get_room(chat_id)
    if room and user_id in room.players:
        player = room.players[user_id]
        player.awaiting_last_letter = False
    await callback.answer("Oxirgi xat bekor qilindi.")
    try:
        await callback.message.edit_text("⏩ <i>Oxirgi xat yozishni rad etdingiz.</i>", parse_mode="HTML")
    except Exception:
        pass

@game_private_router.callback_query(F.data.startswith("act_"))
async def cb_night_action(callback: CallbackQuery):
    parts = callback.data.split("_")
    # act_{chat_id}_{role}_{target_id} or act_{chat_id}_det_{action}_{target_id}
    chat_id = int(parts[1])
    role_str = parts[2]

    if role_str == "det":
        action_type = parts[3]   # "check" or "shoot"
        target_id = int(parts[4])
    else:
        target_id = int(parts[3])
        action_type = "check" if role_str == Role.DETECTIVE.value else None

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

    if role_str in [Role.DON.value, Role.MAFIA.value, Role.LAWYER.value]:
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

    elif role_str == "det" or role_str == Role.DETECTIVE.value:
        if action_type == "shoot":
            room.detective_kill_target = target_id
            await callback.message.edit_text(
                f"🎯 Siz <b>{target_name}</b>ga qarata to'pponchadan o'q uzdingiz!",
                parse_mode="HTML"
            )
            await callback.answer("Nishon mo'ljalga olindi!")
            await room.announce_night_action(callback.bot, Role.DETECTIVE.value)
        else:
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
            await room.announce_night_action(callback.bot, Role.DETECTIVE.value)

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
async def pm_chat_handler(message: Message):
    """Handle private messages: last letter for dead players or secret night chat for mafia."""
    user_id = message.from_user.id
    text = (message.text or message.caption or "").strip()

    # Check if user belongs to an active game room
    room = game_manager.find_user_room(user_id)
    if room and user_id in room.players:
        player = room.players[user_id]

        # Dead player handling (30s last letter window)
        if not player.is_alive:
            if getattr(player, "awaiting_last_letter", False):
                import time
                if time.time() > getattr(player, "last_letter_deadline", 0.0):
                    player.awaiting_last_letter = False
                    return await message.reply("⏳ <b>Vaqt tugadi!</b> 30 soniyalik vaqtingiz o'tib ketgan. O'liklar gapira olmaydi!", parse_mode="HTML")

                player.awaiting_last_letter = False
                if text:
                    clean_letter = html.escape(text[:300])
                    clean_name = html.escape(player.name or "O'yinchi")
                    try:
                        await message.bot.send_message(
                            room.chat_id,
                            f"📜 <b>{clean_name}ning O'lim Oldi Xati:</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"<i>\"{clean_letter}\"</i>\n"
                            f"━━━━━━━━━━━━━━━━━━━━",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                    return await message.reply("📜 <i>Oxirgi xatingiz shaharga yetkazildi!</i>", parse_mode="HTML")
            else:
                return await message.reply("⚠️ <i>Siz o'yinda halok bo'lgansiz. O'liklar gapira olmaydi!</i>", parse_mode="HTML")

        # Living player handling (Mafia night chat)
        if player.is_alive and room.phase == GamePhase.NIGHT and player.team == Team.MAFIA:
            relayed_text = text if text else "[Ovozli xabar / Media]"
            relayed = await room.broadcast_mafia_chat(
                bot=message.bot,
                sender_id=user_id,
                sender_name=message.from_user.first_name,
                text=relayed_text
            )
            if relayed:
                await message.reply("🩸 <i>Xabaringiz Mafiya a'zolariga yetkazildi.</i>", parse_mode="HTML")
            return
