from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from database.crud import get_or_create_user
from database.database import async_session_maker
from locales.i18n import i18n
from services.economy_service import SHOP_ITEMS, buy_shop_item

store_router = Router()

def get_shop_markup(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, item in SHOP_ITEMS.items():
        name = item.get(f"name_{lang}", item.get("name_az", key))
        cost = item["cost"]
        curr = "💰" if item["currency"] == "coins" else "💎"
        btn_text = f"{name} — {cost} {curr}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@store_router.message(Command("shop", "magaza", "dokon"))
async def cmd_shop(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        text = i18n.get(
            "shop_title",
            user.language,
            coins=user.coins,
            diamonds=user.diamonds
        )
        markup = get_shop_markup(user.language)
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

@store_router.callback_query(F.data.startswith("buy_"))
async def cb_buy_item(callback: CallbackQuery):
    item_key = callback.data.replace("buy_", "")
    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        success, result_info = await buy_shop_item(session, callback.from_user.id, item_key)
        
        if success:
            await callback.answer(f"✅ Purchased: {result_info}!", show_alert=True)
            text = i18n.get(
                "shop_title",
                user.language,
                coins=user.coins,
                diamonds=user.diamonds
            )
            try:
                await callback.message.edit_text(text, reply_markup=get_shop_markup(user.language), parse_mode="HTML")
            except Exception:
                pass
        else:
            if result_info == "not_enough_money":
                msg = i18n.get("not_enough_money", user.language)
            else:
                msg = "Could not complete purchase."
            await callback.answer(msg, show_alert=True)
