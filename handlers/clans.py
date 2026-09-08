import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from database.crud import (
    create_clan,
    deposit_to_clan,
    get_clan,
    get_clan_by_tag,
    get_clan_members,
    get_clan_members_count,
    get_or_create_user,
    get_top_clans,
    join_clan,
    leave_clan,
)
from database.database import async_session_maker
from database.models import User
from locales.i18n import i18n
from sqlalchemy import select

clan_router = Router()

def get_clan_no_clan_text(lang: str) -> str:
    return (
        "🛡 <b>Mafia Litsey — Klanlar Tizimi (Mafiya Oilalari)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Siz hozircha hech qaysi klan a'zosi emassiz!</i>\n\n"
        "⚔️ <b>Klan nima beradi?</b>\n"
        "• O'yinda ismingiz oldida klaningiz tegi chiqadi: <b>[LIT] Ism</b>\n"
        "• Jamoadoshlar bilan birgalikda o'ynash va g'alaba qozonish\n"
        "• Har bir g'alaba klan xazinasiga va reytingiga avtomatik hisoblanadi\n"
        "• Klanlararo turnirlar va haftalik Olmos mukofotlari\n\n"
        "👑 <b>Yangi klan ochish narxi:</b> 300 Tanga\n"
        "Buyruq: <code>/clan create [TAG] [Klan Nomi]</code>\n"
        "<i>Misol:</i> <code>/clan create LIT Litsey Mafiya</code>\n\n"
        "🤝 <b>Mavjud klanga qo'shilish:</b> <code>/clan join [TAG]</code>\n"
        "<i>Misol:</i> <code>/clan join LIT</code>\n\n"
        "🏆 <b>Barcha klanlar reytingi:</b> <code>/clan top</code>"
    )

def get_no_clan_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Top Klanlar Reytingi", callback_data="clan_top")],
        [InlineKeyboardButton(text="👥 Asosiy Guruh (@mafia_adu_litsey)", url=settings.MAIN_GROUP_URL)]
    ])

def get_in_clan_markup(clan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 A'zolar Ro'yxati", callback_data=f"clan_members_{clan_id}"),
            InlineKeyboardButton(text="➕ Taklif qilish", callback_data=f"clan_invite_prompt_{clan_id}")
        ],
        [
            InlineKeyboardButton(text="💰 Xazina to'ldirish", callback_data=f"clan_deposit_prompt_{clan_id}"),
            InlineKeyboardButton(text="🏆 Top Klanlar", callback_data="clan_top")
        ],
        [
            InlineKeyboardButton(text="🚪 Klandan Chiqish", callback_data="clan_leave"),
            InlineKeyboardButton(text="👥 Asosiy Guruh", url=settings.MAIN_GROUP_URL)
        ]
    ])

@clan_router.message(Command("clan", "klan"))
async def cmd_clan(message: Message):
    text = (message.text or "").strip()
    args = []
    if text.startswith("/"):
        parts = text.split()
        if len(parts) > 1:
            args = parts[1:]

    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        lang = user.language or settings.DEFAULT_LANGUAGE

        # 1. No arguments: show current clan or create/join prompt
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
                f"🛡 <b>Klan: [{clan.tag}] {clan.name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 <b>Klan Rahbari:</b> <a href=\"tg://user?id={clan.leader_id}\">{html.escape(leader_name)}</a>\n"
                f"👥 <b>A'zolar Soni:</b> <b>{members_count}/20 ta</b>\n"
                f"🏦 <b>Klan Xazinasi:</b> <b>{clan.treasury} Tanga</b>\n"
                f"🏆 <b>Klan Reytingi:</b> <b>{clan.rating} Ball</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Guruhda o'yin yutsangiz, klaningizga avtomatik +15 Ball va +25 Tanga qo'shiladi!</i>\n\n"
                f"➕ <b>Do'stni taklif qilish:</b> <code>/clan invite @username</code>\n"
                f"💰 <b>Xazinani to'ldirish:</b> <code>/clan deposit [miqdor]</code>\n"
                f"👥 <b>A'zolar ro'yxati:</b> <code>/clan members</code>"
            )
            return await message.answer(clan_card, reply_markup=get_in_clan_markup(clan.id), parse_mode="HTML")

        action = args[0].lower()

        # 2. Subcommand: create
        if action in ["create", "yarat", "qur"]:
            if user.clan_id:
                return await message.answer("⚠️ Siz allaqachon klan a'zosisiz! Yangi klan ochish uchun avval klandan chiqing (`/clan leave`).", parse_mode="HTML")

            if len(args) < 3:
                return await message.answer(
                    "ℹ️ <b>Klan yaratish sintaksisi:</b>\n"
                    "<code>/clan create [TAG] [Klan Nomi]</code>\n\n"
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
                f"Do'stlaringizni taklif qilish: <code>/clan invite @username</code>\n"
                f"Klan menyusi: <code>/clan</code>",
                parse_mode="HTML"
            )

        # 3. Subcommand: join
        elif action in ["join", "qoshil", "kir"]:
            if user.clan_id:
                return await message.answer("⚠️ Siz allaqachon biror klan a'zosisiz! Avval klandan chiqing (`/clan leave`).", parse_mode="HTML")

            if len(args) < 2:
                return await message.answer(
                    "ℹ️ <b>Klanga qo'shilish sintaksisi:</b>\n"
                    "<code>/clan join [TAG]</code>\n\n"
                    "<i>Misol:</i> <code>/clan join LIT</code>\n\n"
                    "Barcha klanlar teglari: <code>/clan top</code>",
                    parse_mode="HTML"
                )

            tag = args[1].strip().upper()
            success, reason, clan = await join_clan(session, user.id, tag)
            if success:
                return await message.answer(
                    f"🎉 <b>Tabriklaymiz!</b> Siz muvaffaqiyatli <b>[{clan.tag}] {clan.name}</b> klaniga qabul qilindingiz!\n\n"
                    f"Endi o'yinlarda ismingiz oldida <b>[{clan.tag}]</b> tegi ko'rinadi.\n"
                    f"Klan ma'lumotlari: <code>/clan</code>",
                    parse_mode="HTML"
                )
            else:
                if reason == "clan_not_found":
                    return await message.answer(f"❌ <b>[{tag}]</b> tegiga ega klan topilmadi. Tegni to'g'ri kiritganingizga ishonch hosil qiling.", parse_mode="HTML")
                elif reason == "clan_full":
                    return await message.answer("❌ Bu klan a'zolari to'lgan (maksimum 20 nafar o'yinchi)!", parse_mode="HTML")
                else:
                    return await message.answer("❌ Klanga qo'shilishda xatolik yuz berdi.", parse_mode="HTML")

        # 4. Subcommand: invite
        elif action in ["invite", "taklif", "chaqir"]:
            if not user.clan_id:
                return await message.answer("⚠️ Siz hech qaysi klan a'zosi emassiz! Do'stlarni taklif qilish uchun avval klan yarating yoki qo'shiling.", parse_mode="HTML")

            clan = await get_clan(session, user.clan_id)
            if not clan:
                return await message.answer("⚠️ Klaningiz topilmadi.", parse_mode="HTML")

            if len(args) < 2:
                return await message.answer(
                    "ℹ️ <b>Taklif qilish sintaksisi:</b>\n"
                    "<code>/clan invite @username</code>\n\n"
                    "Yoki do'stingizga quyidagi buyruqni yuboring:\n"
                    f"👉 <code>/clan join {clan.tag}</code>",
                    parse_mode="HTML"
                )

            target_uname = args[1].replace("@", "").strip()
            # Find target user in DB
            stmt = select(User).where(User.username.ilike(target_uname))
            res = await session.execute(stmt)
            target_user = res.scalar_one_or_none()

            invite_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"⚔️ [{clan.tag}] Klaniga Qo'shilish", callback_data=f"clan_join_accept_{clan.id}")]
            ])

            if target_user:
                if target_user.clan_id:
                    return await message.answer(f"⚠️ @{target_uname} allaqachon boshqa klan a'zosi!", parse_mode="HTML")
                # Send direct notification in PM or current chat
                try:
                    await message.bot.send_message(
                        target_user.id,
                        f"✉️ <b>Klan Taklifi!</b>\n\n"
                        f"<b>{html.escape(user.first_name)}</b> sizni <b>[{clan.tag}] {clan.name}</b> klaniga taklif qildi!\n\n"
                        f"Qo'shilish uchun quyidagi tugmani bosing:",
                        reply_markup=invite_markup,
                        parse_mode="HTML"
                    )
                    return await message.answer(f"✅ @{target_uname} foydalanuvchisiga shaxsiy xabarda taklifnoma yuborildi!", parse_mode="HTML")
                except Exception:
                    pass

            # If couldn't send PM, post in chat
            return await message.answer(
                f"✉️ <b>Klan Taklifi!</b>\n\n"
                f"@{target_uname}, sizni <b>[{clan.tag}] {clan.name}</b> klaniga taklif qilishmoqda!\n\n"
                f"Qo'shilish uchun quyidagi tugmani bosing:",
                reply_markup=invite_markup,
                parse_mode="HTML"
            )

        # 5. Subcommand: members
        elif action in ["members", "azolar", "a'zolar"]:
            if not user.clan_id:
                return await message.answer("⚠️ Siz hech qanday klanda emassiz!", parse_mode="HTML")

            clan = await get_clan(session, user.clan_id)
            if not clan:
                return await message.answer("⚠️ Klaningiz topilmadi.", parse_mode="HTML")

            members = await get_clan_members(session, clan.id)
            lines = [f"👥 <b>[{clan.tag}] {clan.name} — A'zolar Ro'yxati ({len(members)}/20):</b>\n"]
            for idx, m in enumerate(members, 1):
                role_badge = "👑 Rahbar" if m.id == clan.leader_id else "⚔️ Jangchi"
                clean_name = html.escape(m.first_name or f"ID {m.id}")
                win_pct = round((m.wins / m.games_played * 100), 1) if m.games_played > 0 else 0
                lines.append(f"{idx}. <a href=\"tg://user?id={m.id}\">{clean_name}</a> ({role_badge}) — Lvl {m.level} ({win_pct}% win)")

            return await message.answer("\n".join(lines), parse_mode="HTML")

        # 6. Subcommand: deposit
        elif action in ["deposit", "tola", "hisob", "xazina"]:
            if len(args) < 2:
                return await message.answer("Foydalanish: <code>/clan deposit &lt;miqdor&gt;</code>\n<i>Misol:</i> <code>/clan deposit 50</code>", parse_mode="HTML")
            try:
                amount = int(args[1])
                if amount <= 0:
                    raise ValueError
            except ValueError:
                return await message.answer("⚠️ To'lov miqdori musbat butun son bo'lishi kerak!", parse_mode="HTML")

            success = await deposit_to_clan(session, message.from_user.id, amount)
            if success:
                return await message.answer(
                    f"✅ <b>+{amount} Tanga</b> klan xazinasiga kiritildi va klan reytingiga ball qo'shildi!",
                    parse_mode="HTML"
                )
            else:
                return await message.answer(
                    "❌ Mablag' yetarli emas yoki siz biror klan a'zosi emassiz!",
                    parse_mode="HTML"
                )

        # 7. Subcommand: leave
        elif action in ["leave", "chiq", "chiqish"]:
            if not user.clan_id:
                return await message.answer("⚠️ Siz hech qanday klanda emassiz!", parse_mode="HTML")

            success = await leave_clan(session, message.from_user.id)
            if success:
                return await message.answer("🚪 Siz klandan muvaffaqiyatli chiqdingiz.", parse_mode="HTML")
            else:
                return await message.answer("❌ Klandan chiqishda xatolik yuz berdi.", parse_mode="HTML")

        # 8. Subcommand: top
        elif action in ["top", "reyting", "liderlar"]:
            clans = await get_top_clans(session, limit=10)
            if not clans:
                return await message.answer("🛡 Hozircha birorta ham klan tashkil etilmagan.", parse_mode="HTML")

            lines = ["🏆 <b>Mafia Litsey — Eng Kuchli Klanlar Reytingi:</b>\n"]
            medals = ["🥇", "🥈", "🥉"]
            for idx, c in enumerate(clans):
                medal = medals[idx] if idx < 3 else f"{idx+1}."
                lines.append(f"{medal} <b>[{c.tag}] {c.name}</b> — 🏆 <b>{c.rating} Ball</b> | 🏦 <b>{c.treasury} Tanga</b>")

            lines.append("\nKlan yaratish: <code>/clan create [TAG] [Nom]</code>\nKlanga qo'shilish: <code>/clan join [TAG]</code>")
            return await message.answer("\n".join(lines), parse_mode="HTML")

        else:
            return await message.answer(
                "🛡 <b>Klan Buyruqlari:</b>\n\n"
                "• <code>/clan</code> — Shaxsiy klan kartasi\n"
                "• <code>/clan create [TAG] [Nom]</code> — Yangi klan ochish (300 Tanga)\n"
                "• <code>/clan join [TAG]</code> — Klanga qo'shilish\n"
                "• <code>/clan invite @user</code> — Do'stni taklif qilish\n"
                "• <code>/clan members</code> — Klan a'zolari ro'yxati\n"
                "• <code>/clan deposit [miqdor]</code> — Xazinaga to'lash\n"
                "• <code>/clan leave</code> — Klandan chiqish\n"
                "• <code>/clan top</code> — Top klanlar reytingi",
                parse_mode="HTML"
            )

@clan_router.callback_query(F.data.startswith("clan_join_accept_"))
async def cb_clan_join_accept(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_join_accept_", ""))
    async with async_session_maker() as session:
        success, reason, clan = await join_clan(session, callback.from_user.id, clan_id)
        if success:
            await callback.answer("Tabriklaymiz, siz klanga qo'shildingiz!")
            await callback.message.answer(
                f"🎉 <b>Tabriklaymiz!</b> Siz <b>[{clan.tag}] {clan.name}</b> klaniga muvaffaqiyatli qo'shildingiz!\n\n"
                f"Endi barcha o'yinlarda ismingiz oldida <b>[{clan.tag}]</b> tegi ko'rinadi.\n"
                f"Klan menyusi: <code>/clan</code>",
                parse_mode="HTML"
            )
        else:
            if reason == "already_in_clan":
                msg = "⚠️ Siz allaqachon biror klan a'zosisiz!"
            elif reason == "clan_full":
                msg = "⚠️ Bu klan a'zolari to'lgan (maksimum 20 kishi)!"
            else:
                msg = "⚠️ Klan topilmadi yoki xatolik yuz berdi."
            await callback.answer(msg, show_alert=True)

@clan_router.callback_query(F.data.startswith("clan_members_"))
async def cb_clan_members(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_members_", ""))
    async with async_session_maker() as session:
        clan = await get_clan(session, clan_id)
        if not clan:
            return await callback.answer("Klan topilmadi.", show_alert=True)
        members = await get_clan_members(session, clan_id)
        lines = [f"👥 <b>[{clan.tag}] {clan.name} — A'zolari ({len(members)}/20):</b>\n"]
        for idx, m in enumerate(members, 1):
            role_badge = "👑 Rahbar" if m.id == clan.leader_id else "⚔️ Jangchi"
            clean_name = html.escape(m.first_name or f"ID {m.id}")
            lines.append(f"{idx}. <a href=\"tg://user?id={m.id}\">{clean_name}</a> ({role_badge}) — Lvl {m.level}")

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="clan_back")]
        ])
        await callback.answer()
        await callback.message.edit_text("\n".join(lines), reply_markup=markup, parse_mode="HTML")

@clan_router.callback_query(F.data.startswith("clan_invite_prompt_"))
async def cb_clan_invite_prompt(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_invite_prompt_", ""))
    async with async_session_maker() as session:
        clan = await get_clan(session, clan_id)
        tag = clan.tag if clan else "TAG"
    await callback.answer()
    await callback.message.answer(
        f"➕ <b>Do'stlarni klanga taklif qilish usullari:</b>\n\n"
        f"1. Do'stingizga qo'shilish buyrug'ini yuboring:\n"
        f"👉 <code>/clan join {tag}</code>\n\n"
        f"2. Botda to'g'ridan-to'g'ri taklifnoma yuboring:\n"
        f"👉 <code>/clan invite @username</code>",
        parse_mode="HTML"
    )

@clan_router.callback_query(F.data.startswith("clan_deposit_prompt_"))
async def cb_clan_deposit_prompt(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💰 <b>Klan xazinasiga mablag' kiritish:</b>\n\n"
        "Buyruq: <code>/clan deposit [miqdor]</code>\n"
        "<i>Misol:</i> <code>/clan deposit 100</code>\n\n"
        "💡 Har 10 tanga klan reytingiga +1 Ball qo'shadi!",
        parse_mode="HTML"
    )

@clan_router.callback_query(F.data == "clan_top")
async def cb_clan_top(callback: CallbackQuery):
    async with async_session_maker() as session:
        clans = await get_top_clans(session, limit=10)
        lines = ["🏆 <b>Mafia Litsey — Eng Kuchli Klanlar Reytingi:</b>\n"]
        if not clans:
            lines.append("<i>Hozircha birorta ham klan tashkil etilmagan.</i>")
        else:
            medals = ["🥇", "🥈", "🥉"]
            for idx, c in enumerate(clans):
                medal = medals[idx] if idx < 3 else f"{idx+1}."
                lines.append(f"{medal} <b>[{c.tag}] {c.name}</b> — 🏆 <b>{c.rating} Ball</b> | 🏦 <b>{c.treasury} Tanga</b>")

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
