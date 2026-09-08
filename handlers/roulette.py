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
    {"type": "coins", "amount": 50, "weight": 40},
    {"type": "coins", "amount": 100, "weight": 25},
    {"type": "coins", "amount": 250, "weight": 15},
    {"type": "diamonds", "amount": 1, "weight": 12},
    {"type": "diamonds", "amount": 3, "weight": 6},
    {"type": "diamonds", "amount": 10, "weight": 2, "jackpot": True},
]

def pick_roulette_prize():
    weights = [p["weight"] for p in ROULETTE_PRIZES]
    return random.choices(ROULETTE_PRIZES, weights=weights, k=1)[0]

def get_prize_label(prize: dict, lang: str) -> str:
    p_type = prize["type"]
    amt = prize["amount"]
    is_jackpot = prize.get("jackpot", False)
    
    if p_type == "coins":
        curr = {
            "uz": "Tanga",
            "az": "Qızıl",
            "ru": "Монет",
            "en": "Coins",
            "tr": "Altın"
        }.get(lang, "Tanga")
        return f"💰 {amt} {curr}"
    else:
        if is_jackpot:
            curr = {
                "uz": "10 OLMOS (JEKPOT!)",
                "az": "10 ALMAZ (CEKPOT!)",
                "ru": "10 АЛМАЗОВ (ДЖЕКПОТ!)",
                "en": "10 DIAMONDS (JACKPOT!)",
                "tr": "10 ELMAS (BÜYÜK İKRAMİYE!)"
            }.get(lang, "10 OLMOS (JEKPOT!)")
            return f"👑 {curr}"
        else:
            curr = {
                "uz": "Olmos",
                "az": "Almaz",
                "ru": "Алмаз" if amt == 1 else "Алмаза",
                "en": "Diamond" if amt == 1 else "Diamonds",
                "tr": "Elmas"
            }.get(lang, "Olmos")
            return f"💎 {amt} {curr}"

@roulette_router.message(Command("roulette", "rulet"))
async def cmd_roulette(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)

    lang = user.language or "uz"
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.get("roulette_btn_spin", lang), callback_data="spin_roulette")]
    ])

    await message.answer(
        i18n.get("roulette_title", lang, coins=user.coins, diamonds=user.diamonds),
        reply_markup=markup,
        parse_mode="HTML"
    )

@roulette_router.callback_query(F.data == "spin_roulette")
async def cb_spin_roulette(callback: CallbackQuery):
    cost = 50
    user_id = callback.from_user.id

    async with async_session_maker() as session:
        user = await get_or_create_user(session, user_id)
        lang = user.language or "uz"
        if user.coins < cost:
            return await callback.answer(i18n.get("not_enough_money", lang), show_alert=True)

        user.coins -= cost
        prize = pick_roulette_prize()
        if prize["type"] == "coins":
            user.coins += prize["amount"]
        elif prize["type"] == "diamonds":
            user.diamonds += prize["amount"]
        await session.commit()

    prize_label = get_prize_label(prize, lang)

    # Animation steps
    frames = [
        i18n.get("roulette_frame_spinning", lang),
        i18n.get("roulette_frame_slowing", lang),
        i18n.get("roulette_result", lang, prize=prize_label, coins=user.coins, diamonds=user.diamonds)
    ]

    for frame in frames[:-1]:
        try:
            await callback.message.edit_text(frame, parse_mode="HTML")
            await asyncio.sleep(1)
        except Exception:
            pass

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.get("roulette_btn_respin", lang), callback_data="spin_roulette")]
    ])
    try:
        await callback.message.edit_text(frames[-1], reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer(i18n.get("roulette_toast", lang, prize=prize_label))
