from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from database.crud import get_active_tournaments, get_or_create_user, get_tournament_participant_count
from database.database import async_session_maker
from locales.i18n import i18n
from services.tournament_engine import (
    create_tournament,
    register_participant,
    get_tournament_standings,
    conclude_tournament,
)

tournament_router = Router()

@tournament_router.message(Command("tournament", "turnir"))
async def cmd_tournament(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        tournaments = await get_active_tournaments(session)

        if not tournaments:
            # Seed a default tournament if none exists
            t = await create_tournament(
                session=session,
                name="Litsey Mafia Cup 2026",
                entry_fee=150,
                prize_pool=100,
                max_participants=16
            )
            tournaments = [t]

        t = tournaments[0]
        reg_count = await get_tournament_participant_count(session, t.id)
        group_btn_text = "👥 Asosiy Guruh: @mafia_adu_litsey" if user.language in ["uz", "az"] else "👥 Main Group: @mafia_adu_litsey"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get("btn_register_tournament", user.language), callback_data=f"reg_tourn_{t.id}")],
            [InlineKeyboardButton(text="📊 Turnir Jadvali (Reyting)", callback_data=f"tourn_standings_{t.id}")],
            [InlineKeyboardButton(text=group_btn_text, url=settings.MAIN_GROUP_URL)]
        ])

        text = i18n.get(
            "tournament_title",
            user.language,
            t_name=t.name,
            prize_pool=t.prize_pool,
            registered=reg_count,
            max_participants=t.max_participants,
            entry_fee=t.entry_fee
        )
        text += (
            f"\n\n📢 <b>Barcha turnir o'yinlari va yangiliklar:</b>\n"
            f"👉 <a href=\"{settings.MAIN_GROUP_URL}\">@{settings.MAIN_GROUP_USERNAME}</a> rasmiy guruhimizda o'tkaziladi!\n\n"
            f"💡 Har bir o'yindagi g'alaba uchun turnir reytingiga <b>+3 Ball</b> beriladi!"
        )
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

@tournament_router.message(Command("newtournament", "yangi_turnir"))
async def cmd_new_tournament(message: Message, command: CommandObject):
    """Admin command to create a new tournament: /newtournament <name> <fee> <prize> [max_p]"""
    user = message.from_user
    is_admin = (user.username and user.username.lower() == "mx767") or (user.id in settings.ADMIN_IDS)
    if not is_admin:
        return await message.reply("⚠️ Ushbu buyruq faqat bot boshqaruvchisi @mx767 uchun ruxsat etilgan!")

    args = (command.args or "").strip().split()
    if len(args) < 3:
        return await message.reply(
            "ℹ️ <b>Turnir yaratish sintaksisi:</b>\n"
            "<code>/newtournament &lt;nomi&gt; &lt;kirish_haqi&gt; &lt;mukofot_olmos&gt; [qatnashuvchilar_soni]</code>\n\n"
            "<i>Misol:</i> <code>/newtournament Bahor_Kubogi 200 500 16</code>",
            parse_mode="HTML"
        )

    name = args[0].replace("_", " ")
    try:
        entry_fee = int(args[1])
        prize_pool = int(args[2])
        max_p = int(args[3]) if len(args) > 3 else 16
    except ValueError:
        return await message.reply("⚠️ Kirish haqi va mukofot raqamda kiritilishi kerak!")

    async with async_session_maker() as session:
        t = await create_tournament(
            session=session,
            name=name,
            entry_fee=entry_fee,
            prize_pool=prize_pool,
            max_participants=max_p
        )
        await message.reply(
            f"🏆 <b>Yangi turnir yaratildi!</b>\n\n"
            f"📌 <b>Nomi:</b> {t.name}\n"
            f"💰 <b>Mukofot:</b> {t.prize_pool} Olmos\n"
            f"🎫 <b>Kirish haqi:</b> {t.entry_fee} Tanga\n"
            f"👥 <b>Maksimal o'yinchilar:</b> {t.max_participants}\n\n"
            f"Guruhlarda /tournament buyrug'i orqali ro'yxatdan o'tishlari mumkin.",
            parse_mode="HTML"
        )

@tournament_router.callback_query(F.data.startswith("reg_tourn_"))
async def cb_register_tournament(callback: CallbackQuery):
    t_id = int(callback.data.replace("reg_tourn_", ""))
    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        success, reason = await register_participant(session, t_id, callback.from_user.id)
        if success:
            msg = f"✅ Siz turnirga ro'yxatdan o'tdingiz!\nTurnir o'yinlari @{settings.MAIN_GROUP_USERNAME} guruhida o'tkaziladi."
            await callback.answer(msg, show_alert=True)
            await callback.message.answer(
                f"🎉 <b>Turnirga qabul qilindingiz!</b>\n\n"
                f"🏆 O'yinlar va e'lonlar uchun asosiy guruhga qo'shiling:\n"
                f"👉 <a href=\"{settings.MAIN_GROUP_URL}\">@{settings.MAIN_GROUP_USERNAME}</a>",
                parse_mode="HTML"
            )
        else:
            if reason == "not_enough_coins":
                msg = i18n.get("not_enough_money", user.language)
            elif reason == "already_registered":
                msg = "⚠️ Siz allaqachon ushbu turnirga ro'yxatdan o'tgansiz!"
            else:
                msg = "⚠️ Turnir to'lgan yoki ro'yxatdan o'tish yopilgan."
            await callback.answer(msg, show_alert=True)

@tournament_router.message(Command("tournstandings", "turnir_jadvali"))
async def cmd_tourn_standings(message: Message):
    async with async_session_maker() as session:
        tournaments = await get_active_tournaments(session)
        if not tournaments:
            return await message.answer("⚠️ Hozirda faol turnir mavjud emas.", parse_mode="HTML")
        t = tournaments[0]
        standings = await get_tournament_standings(session, t.id)
        if not standings:
            return await message.answer(
                f"🏆 <b>{t.name} — Turnir Jadvali:</b>\n\n"
                f"<i>Hozircha birorta ham ishtirokchi ro'yxatdan o'tmagan.</i>\n"
                f"Ro'yxatdan o'tish uchun: <code>/tournament</code>",
                parse_mode="HTML"
            )

        lines = [
            f"🏆 <b>{t.name} — Ishtirokchilar Reytingi:</b>",
            f"💎 Jamg'arma: <b>{t.prize_pool} Olmos</b>\n"
        ]
        medals = ["🥇", "🥈", "🥉"]
        import html
        for idx, (user, part) in enumerate(standings):
            medal = medals[idx] if idx < 3 else f"{idx+1}."
            clean_name = html.escape(user.first_name or f"ID {user.id}")
            lines.append(f"{medal} <a href=\"tg://user?id={user.id}\">{clean_name}</a> — 🎯 <b>{part.points} Ball</b> | Lvl {user.level}")

        lines.append(f"\n📢 Turnir o'yinlari: @{settings.MAIN_GROUP_USERNAME}")
        await message.answer("\n".join(lines), parse_mode="HTML")

@tournament_router.callback_query(F.data.startswith("tourn_standings_"))
async def cb_tourn_standings(callback: CallbackQuery):
    t_id = int(callback.data.replace("tourn_standings_", ""))
    async with async_session_maker() as session:
        from database.models import Tournament
        t = await session.get(Tournament, t_id)
        if not t:
            return await callback.answer("Turnir topilmadi.", show_alert=True)
        standings = await get_tournament_standings(session, t_id)
        if not standings:
            await callback.answer()
            return await callback.message.answer(
                f"🏆 <b>{t.name} — Turnir Jadvali:</b>\n\n"
                f"<i>Hozircha birorta ham ishtirokchi ro'yxatdan o'tmagan.</i>",
                parse_mode="HTML"
            )

        lines = [
            f"🏆 <b>{t.name} — Ishtirokchilar Reytingi:</b>",
            f"💎 Jamg'arma: <b>{t.prize_pool} Olmos</b>\n"
        ]
        medals = ["🥇", "🥈", "🥉"]
        import html
        for idx, (user, part) in enumerate(standings):
            medal = medals[idx] if idx < 3 else f"{idx+1}."
            clean_name = html.escape(user.first_name or f"ID {user.id}")
            lines.append(f"{medal} <a href=\"tg://user?id={user.id}\">{clean_name}</a> — 🎯 <b>{part.points} Ball</b>")

        lines.append(f"\n📢 Turnir o'yinlari: @{settings.MAIN_GROUP_USERNAME}")
        await callback.answer()
        await callback.message.answer("\n".join(lines), parse_mode="HTML")

@tournament_router.message(Command("tournfinish", "turnir_yakunlash"))
async def cmd_tourn_finish(message: Message, command: CommandObject):
    """Admin command to conclude tournament and crown champion: /tournfinish [tournament_id]"""
    user = message.from_user
    is_admin = (user.username and user.username.lower() == "mx767") or (user.id in settings.ADMIN_IDS)
    if not is_admin:
        return await message.reply("⚠️ Ushbu buyruq faqat bot boshqaruvchisi @mx767 uchun ruxsat etilgan!")

    async with async_session_maker() as session:
        tournaments = await get_active_tournaments(session)
        if not tournaments:
            return await message.reply("⚠️ Faol turnir topilmadi.")

        t_id = int(command.args.strip()) if command.args and command.args.strip().isdigit() else tournaments[0].id
        success, champ, prize = await conclude_tournament(session, t_id)
        if not success or not champ:
            return await message.reply("❌ Turnirni yakunlashda xatolik yuz berdi (ishtirokchilar yo'q bo'lishi mumkin).")

        import html
        champ_name = html.escape(champ.first_name or f"ID {champ.id}")
        await message.answer(
            f"🏆 <b>TURNIR RASMAN YAKUNLANDI!</b>\n\n"
            f"🥇 <b>Bosh Chempion:</b> <a href=\"tg://user?id={champ.id}\">{champ_name}</a>\n"
            f"👑 <b>Unvon:</b> <code>🏆 Litsey Chempioni</code>\n"
            f"💎 <b>Mukofot:</b> <b>+{prize} Olmos</b> hisobiga o'tkazildi!\n\n"
            f"Barcha ishtirokchilarga rahmat! Yangi turnir tez orada e'lon qilinadi.",
            parse_mode="HTML"
        )
