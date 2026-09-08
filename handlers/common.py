import random
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from sqlalchemy import select
from database.models import User
from database.crud import (
    claim_daily_bonus,
    get_or_create_group,
    get_or_create_user,
    get_top_players,
    set_group_language,
    set_user_language,
)
from database.database import async_session_maker
from game.enums import GamePhase
from game.manager import game_manager
from locales.i18n import SUPPORTED_LANGUAGES, i18n
from services.economy_service import SHOP_ITEMS, get_user_inventory

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
        "roles": "🎭 Rollar",
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
        "roles": "🎭 Rollar",
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
        "roles": "🎭 Роли",
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
        "roles": "🎭 Roles",
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
        "roles": "🎭 Roller",
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
ROLES_BUTTONS = {b["roles"] for b in MENU_BUTTONS.values()} | {"🎭 Rollar", "🎭 Роли", "🎭 Roles", "🎭 Roller"}
LANG_BUTTONS = {b["lang"] for b in MENU_BUTTONS.values()} | {"🌐 Tilni tanlash", "🌐 Dil seçimi", "🌐 Dil / Lang", "🌐 Сменить язык", "🌐 Language"}

def get_main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    btns = MENU_BUTTONS.get(lang, MENU_BUTTONS["uz"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=btns["play"]), KeyboardButton(text=btns["profile"])],
            [KeyboardButton(text=btns["shop"]), KeyboardButton(text=btns["roulette"])],
            [KeyboardButton(text=btns["daily"]), KeyboardButton(text=btns["tournament"])],
            [KeyboardButton(text=btns["clan"]), KeyboardButton(text=btns["roles"])],
            [KeyboardButton(text=btns["lang"])]
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
async def cmd_start(message: Message, command: CommandObject = None):
    async with async_session_maker() as session:
        if message.chat.type == "private":
            user = await get_or_create_user(
                session=session,
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name or "Player",
                default_lang=settings.DEFAULT_LANGUAGE
            )

            # Check if started with a game join payload
            if command and command.args:
                args = command.args.strip()
                if args.startswith("game_") or args.startswith("join_"):
                    try:
                        chat_id = int(args.split("_", 1)[1])
                        room = game_manager.get_room(chat_id)
                        if room and room.phase == GamePhase.LOBBY:
                            added = room.add_player(user.id, user.first_name, user.username)
                            if added:
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
                                return await message.answer(
                                    f"✅ <b>Siz o'yinga muvaffaqiyatli qo'shildingiz!</b>\n\nIltimos, guruhga qayting va o'yin boshlanishini kuting.",
                                    parse_mode="HTML"
                                )
                            elif user.id in room.players:
                                return await message.answer(
                                    f"ℹ️ Siz allaqachon ushbu o'yinga qo'shilgansiz!\n\nGuruhga qaytib o'yinni kuzatishingiz mumkin.",
                                    parse_mode="HTML"
                                )
                            else:
                                return await message.answer("⚠️ O'yinchilar soni to'lgan!", parse_mode="HTML")
                        else:
                            return await message.answer(
                                "⚠️ Ushbu guruhdagi ro'yxatdan o'tish yakunlangan yoki o'yin topilmadi.",
                                parse_mode="HTML"
                            )
                    except Exception:
                        pass

            text = i18n.get("welcome", user.language, name=user.first_name)
            await message.answer(text, reply_markup=get_main_menu_keyboard(user.language), parse_mode="HTML")

            try:
                me = await message.bot.get_me()
                btn_txt = "➕ Guruhga Qo'shish / Add to Group" if user.language == "uz" else "➕ Qrupa Əlavə Et / Add to Group"
                info_txt = "🎮 Guruhingizda o'yinga boshlash uchun:" if user.language == "uz" else "🎮 Qrupunuzda oyuna başlamaq üçün:"
                add_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=btn_txt, url=f"https://t.me/{me.username}?startgroup=true")],
                    [InlineKeyboardButton(text="👥 Asosiy Guruh (@mafia_adu_litsey)", url=settings.MAIN_GROUP_URL)]
                ])
                await message.answer(info_txt, reply_markup=add_markup)
            except Exception:
                pass
        else:
            group = await get_or_create_group(session, message.chat.id, message.chat.title or "Group", default_lang=settings.DEFAULT_LANGUAGE)
            room = game_manager.get_room(message.chat.id)
            if room and room.phase == GamePhase.LOBBY:
                user_id = message.from_user.id
                is_allowed = (user_id in room.players) or (user_id == room.creator_id) or (user_id in settings.ADMIN_IDS)
                if not is_allowed:
                    return await message.reply("⚠️ O'yinni boshlash uchun avval o'yinga qo'shiling!")
                if len(room.players) < settings.MIN_PLAYERS:
                    return await message.reply(f"⚠️ Kamida {settings.MIN_PLAYERS} ta o'yinchi kerak! (Hozir: {len(room.players)}/{settings.MIN_PLAYERS})")
                await message.reply("🚀 O'yin boshlanmoqda...")
                return await room.start_game(message.bot)

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

        inv_items = await get_user_inventory(session, user.id)
        inv_lines = []
        for key, qty in inv_items.items():
            item_info = SHOP_ITEMS.get(key, {})
            item_name = item_info.get(f"name_{user.language}", item_info.get("name_uz", key))
            inv_lines.append(f"• {item_name}: <b>{qty} ta</b>")

        inv_str = "\n".join(inv_lines) if inv_lines else "<i>(Hozircha bo'sh)</i>"

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
        text += f"\n\n🎒 <b>Inventar:</b>\n{inv_str}\n\n💎 <i>Faol o'yinchilar uchun bepul Olmoslar: admin @mx767</i>"

        btn_map = MENU_BUTTONS.get(user.language, MENU_BUTTONS["uz"])
        shop_txt = btn_map["shop"]
        daily_txt = btn_map["daily"]
        admin_txt = i18n.get("btn_get_diamonds", user.language)

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=shop_txt, callback_data="nav_shop"), InlineKeyboardButton(text=daily_txt, callback_data="nav_daily")],
            [InlineKeyboardButton(text=admin_txt, url="https://t.me/mx767")]
        ])

        await message.answer(text, reply_markup=markup, parse_mode="HTML")

@common_router.callback_query(F.data == "nav_shop")
async def cb_nav_shop(callback: CallbackQuery):
    from handlers.store import cmd_shop
    await callback.answer()
    return await cmd_shop(callback.message)

@common_router.callback_query(F.data == "nav_daily")
async def cb_nav_daily(callback: CallbackQuery):
    await callback.answer()
    return await cmd_daily(callback.message)

@common_router.message(Command("commands"))
async def cmd_commands(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id)
        lang = user.language or settings.DEFAULT_LANGUAGE
    
    text = i18n.get("help", lang)
    await message.answer(text, parse_mode="HTML")

@common_router.message(Command("givegems", "grantgems"))
async def cmd_givegems(message: Message, command: CommandObject = None):
    user = message.from_user
    is_admin = (user.username and user.username.lower() == "mx767") or (user.id in settings.ADMIN_IDS)
    if not is_admin:
        return await message.reply("⚠️ Ushbu buyruq faqat bot administratori (@mx767) uchun!")

    if not command or not command.args:
        return await message.reply("Foydalanish: <code>/givegems @username 50</code> yoki <code>/givegems user_id 50</code>", parse_mode="HTML")

    parts = command.args.strip().split()
    if len(parts) < 2:
        return await message.reply("Foydalanish: <code>/givegems @username 50</code>", parse_mode="HTML")

    target_str = parts[0].lstrip("@")
    try:
        amount = int(parts[1])
    except ValueError:
        return await message.reply("⚠️ Miqdor son bo'lishi kerak!")

    async with async_session_maker() as session:
        target_user = None
        if target_str.isdigit():
            target_user = await session.get(User, int(target_str))
        if not target_user:
            stmt = select(User).where(User.username.ilike(target_str))
            res = await session.execute(stmt)
            target_user = res.scalar_one_or_none()

        if not target_user:
            return await message.reply(f"⚠️ Foydalanuvchi '{target_str}' topilmadi (u kamida 1 marta botni ishga tushirgan bo'lishi kerak).", parse_mode="HTML")

        target_user.diamonds += amount
        await session.commit()

        await message.reply(f"✅ <b>{target_user.first_name}</b> (@{target_user.username or target_user.id}) ga <b>+{amount} Olmos</b> muvaffaqiyatli berildi! Jami olmoslari: <b>{target_user.diamonds}</b> 💎", parse_mode="HTML")

        try:
            await message.bot.send_message(
                target_user.id,
                f"💎 <b>Tabriklaymiz!</b>\nAdministrator @mx767 sizga faol o'yiningiz uchun <b>+{amount} Olmos</b> taqdim etdi!\n\nJami olmoslaringiz: <b>{target_user.diamonds}</b> 💎",
                parse_mode="HTML"
            )
        except Exception:
            pass

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

@common_router.message(F.text.in_(ROLES_BUTTONS))
async def btn_roles(message: Message):
    from handlers.roles import cmd_roles
    return await cmd_roles(message)

@common_router.message(F.text.in_(LANG_BUTTONS))
async def btn_lang(message: Message):
    return await cmd_lang(message)
