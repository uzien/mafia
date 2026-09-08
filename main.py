import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from database.database import init_db
from handlers import (
    clan_router,
    common_router,
    game_group_router,
    game_private_router,
    store_router,
    tournament_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("mafia_bot")

async def main():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please provide a valid BOT_TOKEN in your .env file or environment!")
        sys.exit(1)

    # Initialize SQLite / PostgreSQL tables
    logger.info("Initializing database tables...")
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register Routers
    dp.include_router(common_router)
    dp.include_router(game_group_router)
    dp.include_router(game_private_router)
    dp.include_router(store_router)
    dp.include_router(clan_router)
    dp.include_router(tournament_router)

    logger.info("Starting Mafia Baku Black Telegram Bot polling...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
