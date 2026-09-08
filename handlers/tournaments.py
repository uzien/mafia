from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from database.crud import get_active_tournaments, get_or_create_user
from database.database import async_session_maker
from locales.i18n import i18n
from services.tournament_engine import create_tournament, register_participant

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
                name="Baku Black Cup 2026",
                entry_fee=150,
                prize_pool=100,
                max_participants=16
            )
            tournaments = [t]

        t = tournaments[0]
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get("btn_register_tournament", user.language), callback_data=f"reg_tourn_{t.id}")]
        ])

        text = i18n.get(
            "tournament_title",
            user.language,
            t_name=t.name,
            prize_pool=t.prize_pool,
            registered=1,
            max_participants=t.max_participants,
            entry_fee=t.entry_fee
        )
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

@tournament_router.callback_query(F.data.startswith("reg_tourn_"))
async def cb_register_tournament(callback: CallbackQuery):
    t_id = int(callback.data.replace("reg_tourn_", ""))
    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        success, reason = await register_participant(session, t_id, callback.from_user.id)
        if success:
            await callback.answer(i18n.get("tournament_registered", user.language), show_alert=True)
        else:
            if reason == "not_enough_coins":
                msg = i18n.get("not_enough_money", user.language)
            elif reason == "already_registered":
                msg = "⚠️ You are already enrolled in this tournament!"
            else:
                msg = "⚠️ Tournament is full or registration closed."
            await callback.answer(msg, show_alert=True)
