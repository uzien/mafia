import random
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from database.crud import (
    claim_daily_bonus,
    get_or_create_group,
    get_or_create_user,
    get_top_players,
    set_group_language,
    set_user_language,
)
from database.database import async_session_maker
from locales.i18n import SUPPORTED_LANGUAGES, i18n

common_router = Router()

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

MENU_BUTTONS = {
    "uz": {
        "play": "🎮 O'ynash / Play",
        "profile": "👤 Profil",
        "shop": "🛒 Do'kon",
        "roulette": "🎰 Ruletka",
        "daily": "🎁 Kunlik Bonus",
        "tournament": "🏆 Turnir",
        "clan": "🛡 Klan",
        "lang": "🌐 Tilni tanlash"
    },
    "az": {
        "play": "🎮 Oyna / Play",
        "profile": "👤 Profil",
        "shop": "🛒 Mağaza",
        "roulette": "🎰 Rulet",
        "daily": "🎁 Gündəlik Bonus",
        "tournament": "🏆 Turnir",
        "clan": "🛡 Klan",
        "lang": "🌐 Dil seçimi"
    },
    "ru": {
        "play": "🎮 Играть / Play",
        "profile": "👤 Профиль",
        "shop": "🛒 Магазин",
        "roulette": "🎰 Рулетка",
        "daily": "🎁 Ежедневный Бонус",
        "tournament": "🏆 Турнир",
        "clan": "🛡 Клан",
        "lang": "🌐 Сменить язык"
    },
    "en": {
        "play": "🎮 Play",
        "profile": "👤 Profile",
        "shop": "🛒 Store",
        "roulette": "🎰 Roulette",
        "daily": "🎁 Daily Bonus",
        "tournament": "🏆 Tournament",
        "clan": "🛡 Clan",
        "lang": "🌐 Language"
    },
    "tr": {
        "play": "🎮 Oyna / Play",
        "profile": "👤 Profil",
        "shop": "🛒 Mağaza",
        "roulette": "🎰 Rulet",
        "daily": "🎁 Günlük Bonus",
        "tournament": "🏆 Turnuva",
        "clan": "🛡 Klan",
        "lang": "🌐 Dil seçimi"
    }
}

PLAY_BUTTONS = {b["play"] for b in MENU_BUTTONS.values()} | {"🎮 Oyna / Play", "🎮 O'ynash / Play", "🎮 Играть / Play", "🎮 Play"}
PROFILE_BUTTONS = {b["profile"] for b in MENU_BUTTONS.values()} | {"👤 Profil", "👤 Профиль", "👤 Profile"}
SHOP_BUTTONS = {b["shop"] for b in MENU_BUTTONS.values()} | {"🛒 Do'kon", "🛒 Mağaza", "🛒 Магазин", "🛒 Store", "🛒 Shop"}
ROULETTE_BUTTONS = {b["roulette"] for b in MENU_BUTTONS.values()} | {"🎰 Ruletka", "🎰 Rulet", "🎰 Рулетка", "🎰 Roulette"}
DAILY_BUTTONS = {b["daily"] for b in MENU_BUTTONS.values()} | {"🎁 Kunlik Bonus", "🎁 Gündəlik Bonus", "🎁 Ежедневный Бонус", "🎁 Daily Bonus", "🎁 Günlük Bonus"}
TOURNAMENT_BUTTONS = {b["tournament"] for b in MENU_BUTTONS.values()} | {"🏆 Turnir", "🏆 Турнир", "🏆 Tournament", "🏆 Turnuva"}
CLAN_BUTTONS = {b["clan"] for b in MENU_BUTTONS.values()} | {"🛡 Klan", "🛡 Клан", "🛡 Clan"}
LANG_BUTTONS = {b["lang"] for b in MENU_BUTTONS.values()} | {"🌐 Tilni tanlash", "🌐 Dil seçimi", "🌐 Dil / Lang", "🌐 Сменить язык", "🌐 Language"}

def get_main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    btns = MENU_BUTTONS.get(lang, MENU_BUTTONS["uz"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=btns["play"]), KeyboardButton(text=btns["profile"])],
            [KeyboardButton(text=btns["shop"]), KeyboardButton(text=btns["roulette"])],
            [KeyboardButton(text=btns["daily"]), KeyboardButton(text=btns["tournament"])],
            [KeyboardButton(text=btns["clan"]), KeyboardButton(text=btns["lang"])]
        ],
        resize_keyboard=True
    )

def get_language_markup(prefix: str = "set_lang_") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"{prefix}{code}")]
        for code, name in SUPPORTED_LANGUAGES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@common_router.message(Command("start"))
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        if message.chat.type == "private":
            user = await get_or_create_user(
                session=session,
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name or "Player",
                default_lang=settings.DEFAULT_LANGUAGE
            )
            text = i18n.get("welcome", user.language, name=user.first_name)
            await message.answer(text, reply_markup=get_main_menu_keyboard(user.language), parse_mode="HTML")

            try:
                me = await message.bot.get_me()
                btn_txt = "➕ Guruhga Qo'shish / Add to Group" if user.language == "uz" else "➕ Qrupa Əlavə Et / Add to Group"
                info_txt = "🎮 Guruhingizda o'yinga boshlash uchun:" if user.language == "uz" else "🎮 Qrupunuzda oyuna başlamaq üçün:"
                add_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=btn_txt, url=f"https://t.me/{me.username}?startgroup=true")]
                ])
                await message.answer(info_txt, reply_markup=add_markup)
            except Exception:
                pass
        else:
            group = await get_or_create_group(session, message.chat.id, message.chat.title or "Group", default_lang=settings.DEFAULT_LANGUAGE)
            await message.answer(
                f"👋 <b>{settings.BOT_NAME}</b> faol!\nO'yinni boshlash uchun <code>/game</code> buyrug'ini yuboring.",
                parse_mode="HTML"
            )

@common_router.message(Command("help"))
async def cmd_help(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await message.answer(i18n.get("help", user.language), parse_mode="HTML")

@common_router.message(Command("lang"))
async def cmd_lang(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await message.answer(
            i18n.get("choose_lang", user.language),
            reply_markup=get_language_markup("user_lang_"),
            parse_mode="HTML"
        )

@common_router.callback_query(F.data.startswith("user_lang_"))
async def cb_user_lang(callback: CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    async with async_session_maker() as session:
        await set_user_language(session, callback.from_user.id, lang_code)
        lang_name = SUPPORTED_LANGUAGES.get(lang_code, lang_code)
        await callback.message.edit_text(
            i18n.get("lang_changed", lang_code, lang_name=lang_name),
            parse_mode="HTML"
        )
        if callback.message.chat.type == "private":
            await callback.message.answer(
                f"✅ {lang_name}",
                reply_markup=get_main_menu_keyboard(lang_code)
            )
    await callback.answer()

@common_router.message(Command("setlang"))
async def cmd_setlang(message: Message):
    if message.chat.type == "private":
        return await cmd_lang(message)
    await message.answer(
        "🌐 Choose group language / Qrup dilini seçin / Guruh tilini tanlang:",
        reply_markup=get_language_markup("group_lang_"),
        parse_mode="HTML"
    )

@common_router.callback_query(F.data.startswith("group_lang_"))
async def cb_group_lang(callback: CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    async with async_session_maker() as session:
        await set_group_language(session, callback.message.chat.id, lang_code)
        lang_name = SUPPORTED_LANGUAGES.get(lang_code, lang_code)
        await callback.message.edit_text(
            f"✅ Group language set to: <b>{lang_name}</b>",
            parse_mode="HTML"
        )
    await callback.answer()

@common_router.message(Command("profile"))
async def cmd_profile(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        win_rate = round((user.wins / user.games_played * 100), 1) if user.games_played > 0 else 0
        best_role_name = i18n.get(f"roles.{user.best_role}", user.language)

        text = i18n.get(
            "profile_card",
            user.language,
            name=user.first_name,
            title=user.title,
            level=user.level,
            exp=user.exp,
            coins=user.coins,
            diamonds=user.diamonds,
            games_played=user.games_played,
            wins=user.wins,
            losses=user.losses,
            win_rate=win_rate,
            best_role=best_role_name
        )
        await message.answer(text, parse_mode="HTML")

@common_router.message(Command("daily"))
async def cmd_daily(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        bonus = random.randint(settings.DAILY_BONUS_MIN, settings.DAILY_BONUS_MAX)
        success, hours = await claim_daily_bonus(session, message.from_user.id, bonus)
        if success:
            text = i18n.get("daily_bonus_success", user.language, amount=bonus)
        else:
            text = i18n.get("daily_bonus_already", user.language, hours=hours)
        await message.answer(text, parse_mode="HTML")

@common_router.message(Command("top"))
async def cmd_top(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id)
        top_users = await get_top_players(session, limit=10)
        
        lines = [f"🏆 <b>Top Mafia Litsey Players:</b>\n"]
        for idx, u in enumerate(top_users):
            medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
            lines.append(f"{medal} <b>{u.first_name}</b> — 🏆 {u.wins} Wins | ⭐ Lvl {u.level} | 💰 {u.coins}")

        await message.answer("\n".join(lines), parse_mode="HTML")

# Reply Keyboard Text Button Handlers
@common_router.message(F.text.in_(PLAY_BUTTONS))
async def btn_play(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id)
        lang = user.language or settings.DEFAULT_LANGUAGE
    try:
        me = await message.bot.get_me()
        btn_txt = "➕ Guruhga Qo'shish / Add to Group" if lang == "uz" else "➕ Qrupa Əlavə Et / Add to Group"
        msg_txt = (
            "🕶 <b>Mafiya o'yini guruhlarda o'ynaladi!</b>\nMeni guruhingizga qo'shib <code>/game</code> buyrug'ini yuboring:"
            if lang == "uz" else
            "🕶 <b>Mafiya oyunu qruplarda oynanılır!</b>\nMəni qrupunuza əlavə edib <code>/game</code> yazın:"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_txt, url=f"https://t.me/{me.username}?startgroup=true")]
        ])
        await message.answer(msg_txt, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass

@common_router.message(F.text.in_(PROFILE_BUTTONS))
async def btn_profile(message: Message):
    return await cmd_profile(message)

@common_router.message(F.text.in_(SHOP_BUTTONS))
async def btn_shop(message: Message):
    from handlers.store import cmd_shop
    return await cmd_shop(message)

@common_router.message(F.text.in_(ROULETTE_BUTTONS))
async def btn_roulette(message: Message):
    from handlers.roulette import cmd_roulette
    return await cmd_roulette(message)

@common_router.message(F.text.in_(DAILY_BUTTONS))
async def btn_daily(message: Message):
    return await cmd_daily(message)

@common_router.message(F.text.in_(TOURNAMENT_BUTTONS))
async def btn_tournament(message: Message):
    from handlers.tournaments import cmd_tournament
    return await cmd_tournament(message)

@common_router.message(F.text.in_(CLAN_BUTTONS))
async def btn_clan(message: Message):
    from handlers.clans import cmd_clan
    return await cmd_clan(message)

@common_router.message(F.text.in_(LANG_BUTTONS))
async def btn_lang(message: Message):
    return await cmd_lang(message)
