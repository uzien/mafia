import asyncio
import random
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from database.crud import get_or_create_user
from database.database import async_session_maker
from locales.i18n import i18n

roulette_router = Router()

ROULETTE_PRIZES = [
    {"type": "coins", "amount": 50, "label": "💰 50 Qızıl", "weight": 40},
    {"type": "coins", "amount": 100, "label": "💰 100 Qızıl", "weight": 25},
    {"type": "coins", "amount": 250, "label": "💰 250 Qızıl", "weight": 15},
    {"type": "diamonds", "amount": 1, "label": "💎 1 Almaz", "weight": 12},
    {"type": "diamonds", "amount": 3, "label": "💎 3 Almaz", "weight": 6},
    {"type": "diamonds", "amount": 10, "label": "👑 10 ALMAZ (JACKPOT!)", "weight": 2},
]

def pick_roulette_prize():
    weights = [p["weight"] for p in ROULETTE_PRIZES]
    return random.choices(ROULETTE_PRIZES, weights=weights, k=1)[0]

@roulette_router.message(Command("roulette", "rulet"))
async def cmd_roulette(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Çarxı Fırlat (50 Qızıl) / Spin Wheel", callback_data="spin_roulette")]
    ])

    await message.answer(
        f"🎰 <b>Mafia Baku Black Bəxt Çarxı (Roulette)</b>\n\n"
        f"Balansınız: <b>{user.coins} Qızıl</b> | <b>{user.diamonds} Almaz</b>\n\n"
        f"🎯 <b>Mükafatlar:</b>\n"
        f"• 💰 50 – 250 Qızıl\n"
        f"• 💎 1 – 3 Almaz\n"
        f"• 👑 <b>10 ALMAZ JACKPOT!</b>\n\n"
        f"Bir fırlatma haqqı: <b>50 Qızıl</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )

@roulette_router.callback_query(F.data == "spin_roulette")
async def cb_spin_roulette(callback: CallbackQuery):
    cost = 50
    user_id = callback.from_user.id

    async with async_session_maker() as session:
        user = await get_or_create_user(session, user_id)
        if user.coins < cost:
            return await callback.answer(i18n.get("not_enough_money", user.language), show_alert=True)

        user.coins -= cost
        prize = pick_roulette_prize()
        if prize["type"] == "coins":
            user.coins += prize["amount"]
        elif prize["type"] == "diamonds":
            user.diamonds += prize["amount"]
        await session.commit()

    # Animation steps
    frames = [
        "🎰 <b>[ 🔴 | 🟡 | 🟢 ]</b>\n<i>Çarx sürətlə fırlanır...</i>",
        "🎰 <b>[ 💎 | 💰 | 👑 ]</b>\n<i>Yavaşlayır...</i>",
        f"🎉 <b>TƏBRİKLƏR!</b>\n\nSizin qazancınız: <b>{prize['label']}</b>!\n💰 Cari balans: <b>{user.coins} Qızıl</b> | <b>{user.diamonds} Almaz</b>"
    ]

    for frame in frames[:-1]:
        try:
            await callback.message.edit_text(frame, parse_mode="HTML")
            await asyncio.sleep(1)
        except Exception:
            pass

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Yenidən Fırlat (50 Qızıl)", callback_data="spin_roulette")]
    ])
    try:
        await callback.message.edit_text(frames[-1], reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer(f"🎉 Qazandınız: {prize['label']}!")
