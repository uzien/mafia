from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from database.crud import (
    create_clan,
    deposit_to_clan,
    get_clan,
    get_clan_members_count,
    get_or_create_user,
    get_top_clans,
    leave_clan,
)
from database.database import async_session_maker
from locales.i18n import i18n

clan_router = Router()

def get_clan_no_clan_text(lang: str) -> str:
    if lang == "uz":
        return (
            "🛡 <b>Mafia Litsey — Klanlar Tizimi</b>\n\n"
            "Siz hozircha hech qaysi klan a'zosi emassiz!\n\n"
            "⚔️ <b>Klan nima beradi?</b>\n"
            "• Jamoadoshlar bilan birgalikda o'ynash\n"
            "• Klan xazinasiga hissa qo'shib reytingda ko'tarilish\n"
            "• Klanlararo turnirlar va maxsus mukofotlar\n\n"
            "👑 <b>Yangi klan ochish narxi:</b> 300 Tanga\n"
            "Buyruq: <code>/clan create [TAG] [Klan Nomi]</code>\n"
            "<i>Misol:</i> <code>/clan create LIT Litsey Mafiya</code>\n\n"
            "👥 <b>Barcha klanlar reytingi:</b> <code>/clan top</code>"
        )
    elif lang == "az":
        return (
            "🛡 <b>Mafia Litsey — Klan Sistemi</b>\n\n"
            "Siz hələ heç bir klanın üzvü deyilsiniz!\n\n"
            "⚔️ <b>Klan nə verir?</b>\n"
            "• Komanda yoldaşları ilə birlikdə oynamaq\n"
            "• Klan xəzinəsinə töhfə verib reytinqdə yüksəlmək\n"
            "• Klan turnirləri və xüsusi mükafatlar\n\n"
            "👑 <b>Yeni klan yaratmaq qiyməti:</b> 300 Qızıl\n"
            "Əmr: <code>/clan create [TAG] [Klan Adı]</code>\n"
            "<i>Məsələn:</i> <code>/clan create LIT Litsey Mafiya</code>\n\n"
            "👥 <b>Bütün klanların reytinqi:</b> <code>/clan top</code>"
        )
    elif lang == "ru":
        return (
            "🛡 <b>Система Кланов Mafia Litsey</b>\n\n"
            "Вы пока не состоите ни в одном клане!\n\n"
            "⚔️ <b>Что дает клан?</b>\n"
            "• Совместная игра с соклановцами\n"
            "• Вклады в казну и рост в таблице лидеров\n"
            "• Клановые турниры и уникальные награды\n\n"
            "👑 <b>Стоимость создания клана:</b> 300 Монет\n"
            "Команда: <code>/clan create [ТЕГ] [Название Клана]</code>\n"
            "<i>Пример:</i> <code>/clan create LIT Litsey Mafia</code>\n\n"
            "👥 <b>Рейтинг кланов:</b> <code>/clan top</code>"
        )
    else:
        return (
            "🛡 <b>Mafia Litsey — Clan System</b>\n\n"
            "You are not a member of any clan yet!\n\n"
            "⚔️ <b>Why join a clan?</b>\n"
            "• Play together with teammates\n"
            "• Contribute to the treasury and climb rankings\n"
            "• Clan tournaments & exclusive rewards\n\n"
            "👑 <b>Create Clan Cost:</b> 300 Coins\n"
            "Command: <code>/clan create [TAG] [Clan Name]</code>\n"
            "<i>Example:</i> <code>/clan create LIT Litsey Mafia</code>\n\n"
            "👥 <b>Clan Leaderboard:</b> <code>/clan top</code>"
        )

def get_no_clan_markup(lang: str) -> InlineKeyboardMarkup:
    top_btn = "🏆 Top Klanlar" if lang in ["uz", "az"] else "🏆 Top Clans"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=top_btn, callback_data="clan_top")],
        [InlineKeyboardButton(text="👥 Asosiy Guruh (@mafia_adu_litsey)", url=settings.MAIN_GROUP_URL)]
    ])

def get_in_clan_markup(lang: str) -> InlineKeyboardMarkup:
    top_btn = "🏆 Top Klanlar" if lang in ["uz", "az"] else "🏆 Top Clans"
    leave_btn = "🚪 Klandan Chiqish" if lang in ["uz", "az"] else "🚪 Leave Clan"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=top_btn, callback_data="clan_top")],
        [InlineKeyboardButton(text=leave_btn, callback_data="clan_leave")],
        [InlineKeyboardButton(text="👥 Asosiy Guruh (@mafia_adu_litsey)", url=settings.MAIN_GROUP_URL)]
    ])

@clan_router.message(Command("clan", "klan"))
async def cmd_clan(message: Message):
    text = (message.text or "").strip()
    # Check if message is a command or reply button
    args = []
    if text.startswith("/"):
        parts = text.split()
        if len(parts) > 1:
            args = parts[1:]

    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        lang = user.language or settings.DEFAULT_LANGUAGE

        # 1. No arguments: show current clan or create prompt
        if not args:
            if not user.clan_id:
                return await message.answer(
                    get_clan_no_clan_text(lang),
                    reply_markup=get_no_clan_markup(lang),
                    parse_mode="HTML"
                )
            
            clan = await get_clan(session, user.clan_id)
            if not clan:
                user.clan_id = None
                await session.commit()
                return await message.answer(
                    get_clan_no_clan_text(lang),
                    reply_markup=get_no_clan_markup(lang),
                    parse_mode="HTML"
                )

            members_count = await get_clan_members_count(session, clan.id)
            leader_user = await get_or_create_user(session, clan.leader_id)
            leader_name = leader_user.first_name if leader_user else f"ID: {clan.leader_id}"

            clan_card = (
                f"🛡 <b>Klan: [{clan.tag}] {clan.name}</b>\n\n"
                f"👑 <b>Klan Rahbari:</b> <a href=\"tg://user?id={clan.leader_id}\">{leader_name}</a>\n"
                f"👥 <b>A'zolar:</b> <b>{members_count}/20</b>\n"
                f"🏦 <b>Klan Xazinasi:</b> <b>{clan.treasury} Tanga</b>\n"
                f"🏆 <b>Klan Reytingi:</b> <b>{clan.rating} Ball</b>\n\n"
                f"💰 <b>Xazinani to'ldirish:</b> <code>/clan deposit &lt;miqdor&gt;</code>\n"
                f"🚪 <b>Klandan chiqish:</b> <code>/clan leave</code>"
            )
            return await message.answer(clan_card, reply_markup=get_in_clan_markup(lang), parse_mode="HTML")

        action = args[0].lower()

        # 2. Subcommand: create
        if action in ["create", "yarat", "qur"]:
            if user.clan_id:
                return await message.answer("⚠️ Siz allaqachon klan a'zosisiz! Avval klandan chiqing.", parse_mode="HTML")
            
            if len(args) < 3:
                return await message.answer(
                    "Foydalanish: <code>/clan create [TAG] [Klan Nomi]</code>\n"
                    "<i>Misol:</i> <code>/clan create LIT Litsey Mafiya</code>",
                    parse_mode="HTML"
                )

            tag = args[1][:6].upper()
            name = " ".join(args[2:])[:32]

            if len(tag) < 2:
                return await message.answer("⚠️ Klan tegi kamida 2 ta harfdan iborat bo'lishi kerak!", parse_mode="HTML")
            if len(name) < 3:
                return await message.answer("⚠️ Klan nomi kamida 3 ta belgidan iborat bo'lishi kerak!", parse_mode="HTML")

            CREATE_COST = 300
            if user.coins < CREATE_COST:
                return await message.answer(
                    f"❌ Klan yaratish uchun hisobingizda kamida <b>{CREATE_COST} Tanga</b> bo'lishi kerak!\n"
                    f"Sizning balansingiz: <b>{user.coins} Tanga</b>.",
                    parse_mode="HTML"
                )

            clan = await create_clan(session, message.from_user.id, name, tag)
            if not clan:
                return await message.answer("⚠️ Ushbu nom yoki teg bilan klan allaqachon mavjud!", parse_mode="HTML")

            user.coins -= CREATE_COST
            await session.commit()

            return await message.answer(
                f"🎉 <b>Tabriklaymiz!</b> <b>[{tag}] {name}</b> klani muvaffaqiyatli tashkil etildi!\n\n"
                f"👑 Siz klan yetakchisisiz.\n"
                f"Klan menyusini ochish: <code>/clan</code>",
                parse_mode="HTML"
            )

        # 3. Subcommand: deposit
        elif action in ["deposit", "tola", "hisob", "yatir"]:
            if len(args) < 2:
                return await message.answer("Foydalanish: <code>/clan deposit &lt;miqdor&gt;</code>", parse_mode="HTML")
            try:
                amount = int(args[1])
                if amount <= 0:
                    raise ValueError
            except ValueError:
                return await message.answer("⚠️ To'lov miqdori musbat butun son bo'lishi kerak!", parse_mode="HTML")

            success = await deposit_to_clan(session, message.from_user.id, amount)
            if success:
                return await message.answer(
                    f"✅ <b>+{amount} Tanga</b> klan xazinasiga kiritildi va klan reytingi oshdi!",
                    parse_mode="HTML"
                )
            else:
                return await message.answer(
                    "❌ Mablag' yetarli emas yoki siz biror klan a'zosi emassiz!",
                    parse_mode="HTML"
                )

        # 4. Subcommand: leave
        elif action in ["leave", "chiq", "chiqish"]:
            if not user.clan_id:
                return await message.answer("⚠️ Siz hech qanday klanda emassiz!", parse_mode="HTML")

            success = await leave_clan(session, message.from_user.id)
            if success:
                return await message.answer("🚪 Siz klandan muvaffaqiyatli chiqdingiz.", parse_mode="HTML")
            else:
                return await message.answer("❌ Klandan chiqishda xatolik yuz berdi.", parse_mode="HTML")

        # 5. Subcommand: top
        elif action in ["top", "reyting", "liderlar"]:
            clans = await get_top_clans(session, limit=10)
            if not clans:
                return await message.answer("🛡 Hozircha birorta ham klan tashkil etilmagan.", parse_mode="HTML")

            lines = ["🏆 <b>Mafia Litsey — Eng Kuchli Klanlar:</b>\n"]
            medals = ["🥇", "🥈", "🥉"]
            for idx, c in enumerate(clans):
                medal = medals[idx] if idx < 3 else f"{idx+1}."
                lines.append(f"{medal} <b>[{c.tag}] {c.name}</b> — 🏆 {c.rating} Ball | 🏦 {c.treasury} Tanga")

            lines.append("\nKlan yaratish uchun: <code>/clan create [TAG] [Nom]</code>")
            return await message.answer("\n".join(lines), parse_mode="HTML")

        else:
            return await message.answer(
                "🛡 <b>Klan Buyruqlari:</b>\n\n"
                "• <code>/clan</code> — Klan haqida ma'lumot\n"
                "• <code>/clan create [TAG] [Nom]</code> — Yangi klan ochish (300 Tanga)\n"
                "• <code>/clan deposit [miqdor]</code> — Xazinaga to'lash\n"
                "• <code>/clan leave</code> — Klandan chiqish\n"
                "• <code>/clan top</code> — Top klanlar reytingi",
                parse_mode="HTML"
            )

@clan_router.callback_query(F.data == "clan_top")
async def cb_clan_top(callback: CallbackQuery):
    async with async_session_maker() as session:
        clans = await get_top_clans(session, limit=10)
        lines = ["🏆 <b>Mafia Litsey — Eng Kuchli Klanlar:</b>\n"]
        if not clans:
            lines.append("<i>Hozircha birorta ham klan mavjud emas.</i>")
        else:
            medals = ["🥇", "🥈", "🥉"]
            for idx, c in enumerate(clans):
                medal = medals[idx] if idx < 3 else f"{idx+1}."
                lines.append(f"{medal} <b>[{c.tag}] {c.name}</b> — 🏆 {c.rating} Ball | 🏦 {c.treasury} Tanga")

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="clan_back")]
        ])
        await callback.message.edit_text("\n".join(lines), reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@clan_router.callback_query(F.data == "clan_leave")
async def cb_clan_leave(callback: CallbackQuery):
    async with async_session_maker() as session:
        success = await leave_clan(session, callback.from_user.id)
        if success:
            await callback.answer("🚪 Klandan chiqdingiz!", show_alert=True)
            await callback.message.edit_text(
                "🚪 Siz klandan chiqdingiz.\nYangi klan yaratish uchun <code>/clan create [TAG] [Nom]</code> buyrug'idan foydalaning.",
                parse_mode="HTML"
            )
        else:
            await callback.answer("⚠️ Siz klanda emassiz!", show_alert=True)

@clan_router.callback_query(F.data == "clan_back")
async def cb_clan_back(callback: CallbackQuery):
    await callback.answer()
    return await cmd_clan(callback.message)
