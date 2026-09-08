import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import settings
from database.crud import admin_add_currency, get_all_user_ids
from database.database import async_session_maker

admin_router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    async with async_session_maker() as session:
        user_ids = await get_all_user_ids(session)
    await message.answer(
        f"👑 <b>Mafia Baku Black Superadmin Panel</b>\n\n"
        f"👥 Total Registered Users: <b>{len(user_ids)}</b>\n\n"
        f"<b>Admin Commands:</b>\n"
        f"• <code>/broadcast &lt;message&gt;</code> — Send global message\n"
        f"• <code>/addcoins &lt;user_id&gt; &lt;amount&gt;</code> — Give coins\n"
        f"• <code>/adddiamonds &lt;user_id&gt; &lt;amount&gt;</code> — Give diamonds",
        parse_mode="HTML"
    )

@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return

    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        return await message.answer("Usage: <code>/broadcast &lt;announcement text&gt;</code>", parse_mode="HTML")

    async with async_session_maker() as session:
        user_ids = await get_all_user_ids(session)

    sent = 0
    failed = 0
    status_msg = await message.answer(f"📢 Starting broadcast to {len(user_ids)} users...")

    for u_id in user_ids:
        try:
            await message.bot.send_message(
                u_id,
                f"📢 <b>Rəsmi Elan / Announcement:</b>\n\n{text}",
                parse_mode="HTML"
            )
            sent += 1
            await asyncio.sleep(0.05)  # Rate limit compliance
        except Exception:
            failed += 1

    await status_msg.edit_text(f"✅ Broadcast finished!\nSent: <b>{sent}</b> | Failed: <b>{failed}</b>", parse_mode="HTML")

@admin_router.message(Command("addcoins"))
async def cmd_addcoins(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if len(args) < 2:
        return await message.answer("Usage: <code>/addcoins &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")
    try:
        user_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        return await message.answer("Invalid user_id or amount.", parse_mode="HTML")

    async with async_session_maker() as session:
        success = await admin_add_currency(session, user_id, coins=amount)

    if success:
        await message.answer(f"✅ Successfully added <b>{amount} Coins</b> to user <code>{user_id}</code>!", parse_mode="HTML")
    else:
        await message.answer(f"❌ User <code>{user_id}</code> not found in database.", parse_mode="HTML")

@admin_router.message(Command("adddiamonds"))
async def cmd_adddiamonds(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if len(args) < 2:
        return await message.answer("Usage: <code>/adddiamonds &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")
    try:
        user_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        return await message.answer("Invalid user_id or amount.", parse_mode="HTML")

    async with async_session_maker() as session:
        success = await admin_add_currency(session, user_id, diamonds=amount)

    if success:
        await message.answer(f"✅ Successfully added <b>{amount} Diamonds</b> to user <code>{user_id}</code>!", parse_mode="HTML")
    else:
        await message.answer(f"❌ User <code>{user_id}</code> not found in database.", parse_mode="HTML")
