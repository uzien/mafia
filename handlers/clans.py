from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from database.crud import create_clan, get_clan, get_or_create_user
from database.database import async_session_maker
from locales.i18n import i18n

clan_router = Router()

@clan_router.message(Command("clan", "klan"))
async def cmd_clan(message: Message):
    args = message.text.split()[1:] if message.text else []
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)

        if not args:
            if not user.clan_id:
                return await message.answer(
                    "🛡 <b>Mafia Family (Clan) System</b>\n\n"
                    "You are not a member of any clan yet!\n\n"
                    "<b>To establish a clan:</b>\n"
                    "<code>/clan create [TAG] [Clan Name]</code>\n"
                    "<i>Example:</i> <code>/clan create BK Baku Mafia</code>",
                    parse_mode="HTML"
                )
            clan = await get_clan(session, user.clan_id)
            if not clan:
                return await message.answer("⚠️ Clan not found.", parse_mode="HTML")

            text = i18n.get(
                "clan_info",
                user.language,
                clan_name=f"[{clan.tag}] {clan.name}",
                leader=clan.leader_id,
                members_count=1,
                treasury=clan.treasury,
                rating=clan.rating
            )
            return await message.answer(text, parse_mode="HTML")

        action = args[0].lower()
        if action == "create":
            if len(args) < 3:
                return await message.answer("Usage: <code>/clan create [TAG] [Name]</code>", parse_mode="HTML")
            tag = args[1][:6].upper()
            name = " ".join(args[2:])[:32]

            clan = await create_clan(session, message.from_user.id, name, tag)
            if not clan:
                return await message.answer("⚠️ A clan with this name or tag already exists!", parse_mode="HTML")

            text = i18n.get("clan_created", user.language, clan_name=f"[{tag}] {name}")
            await message.answer(text, parse_mode="HTML")

        elif action in ["deposit", "yatir"]:
            if len(args) < 2:
                return await message.answer("Usage: <code>/clan deposit &lt;amount&gt;</code>", parse_mode="HTML")
            try:
                amount = int(args[1])
                if amount <= 0:
                    raise ValueError
            except ValueError:
                return await message.answer("Invalid deposit amount.", parse_mode="HTML")

            from database.crud import deposit_to_clan
            success = await deposit_to_clan(session, message.from_user.id, amount)
            if success:
                await message.answer(f"✅ <b>+{amount} Qızıl</b> klan xəzinəsinə yatırıldı!", parse_mode="HTML")
            else:
                await message.answer("❌ Kifayət qədər qızılınız yoxdur və ya klanda deyilsiniz!", parse_mode="HTML")
