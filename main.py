import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from database.database import init_db
from handlers import (
    admin_router,
    clan_router,
    common_router,
    game_group_router,
    game_private_router,
    roles_router,
    roulette_router,
    store_router,
    tournament_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("mafia_bot")

import os
from aiohttp import web

async def health_check(request):
    return web.Response(text="Mafia Litsey Telegram Bot is alive and running!", content_type="text/plain")

async def start_web_server(port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Render health check server successfully listening on 0.0.0.0:{port}")
    return runner

from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeDefault

COMMANDS_BY_LANG = {
    "uz": {
        "private": [
            BotCommand(command="profile", description="👤 Shaxsiy profil va balans"),
            BotCommand(command="shop", description="🛒 Do'kon (Kartalar, soxta hujjat)"),
            BotCommand(command="daily", description="🎁 Kunlik bepul tanga bonusi"),
            BotCommand(command="roulette", description="🎰 Omad g'ildiragi (Ruletka)"),
            BotCommand(command="tournament", description="🏆 Turnirlar va sovrinlar"),
            BotCommand(command="clan", description="🛡 Mafiya oilasi (Klan)"),
            BotCommand(command="top", description="📊 Eng kuchli o'yinchilar"),
            BotCommand(command="roles", description="🎭 O'yindagi barcha rollar"),
            BotCommand(command="commands", description="📋 Barcha buyruqlar ro'yxati"),
            BotCommand(command="lang", description="🌐 Tilni o'zgartirish"),
            BotCommand(command="help", description="📖 Yordam va o'yin qoidalari"),
        ],
        "group": [
            BotCommand(command="game", description="🎮 Yangi Mafiya o'yini ochish"),
            BotCommand(command="start", description="🚀 O'yinni tezroq boshlash"),
            BotCommand(command="extend", description="⏳ Ro'yxatga vaqt qo'shish (+30s)"),
            BotCommand(command="roles", description="🎭 Rollar ma'lumotnomasi"),
            BotCommand(command="stop", description="🛑 O'yinni to'xtatish (Admin)"),
            BotCommand(command="setlang", description="🌐 Guruh tilini tanlash"),
            BotCommand(command="help", description="📖 Guruh buyruqlari va qoidalar"),
        ]
    },
    "az": {
        "private": [
            BotCommand(command="profile", description="👤 Şəxsi profil və balans"),
            BotCommand(command="shop", description="🛒 Mağaza (Kartlar, saxta sənəd)"),
            BotCommand(command="daily", description="🎁 Gündəlik bonus"),
            BotCommand(command="roulette", description="🎰 Bəxt çarxı (Rulet)"),
            BotCommand(command="tournament", description="🏆 Turnirlər və kuboklar"),
            BotCommand(command="clan", description="🛡 Mafiya klanı"),
            BotCommand(command="top", description="📊 Liderlər cədvəli"),
            BotCommand(command="roles", description="🎭 Oyundakı bütün rollar"),
            BotCommand(command="commands", description="📋 Bütün əmrlər"),
            BotCommand(command="lang", description="🌐 Dil seçimi"),
            BotCommand(command="help", description="📖 Kömək və qaydalar"),
        ],
        "group": [
            BotCommand(command="game", description="🎮 Yeni oyun otağı açmaq"),
            BotCommand(command="start", description="🚀 Oyunu indi başlat"),
            BotCommand(command="extend", description="⏳ Vaxtı uzatmaq (+30s)"),
            BotCommand(command="roles", description="🎭 Rollar haqqında"),
            BotCommand(command="stop", description="🛑 Oyunu dayandırmaq"),
            BotCommand(command="setlang", description="🌐 Qrup dilini seçmək"),
            BotCommand(command="help", description="📖 Əmrlər və kömək"),
        ]
    },
    "ru": {
        "private": [
            BotCommand(command="profile", description="👤 Профиль и баланс"),
            BotCommand(command="shop", description="🛒 Магазин (Карты, документы)"),
            BotCommand(command="daily", description="🎁 Ежедневный бонус"),
            BotCommand(command="roulette", description="🎰 Колесо удачи (Рулетка)"),
            BotCommand(command="tournament", description="🏆 Турниры и кубки"),
            BotCommand(command="clan", description="🛡 Клан Мафии"),
            BotCommand(command="top", description="📊 Топ игроков"),
            BotCommand(command="roles", description="🎭 Все роли в игре"),
            BotCommand(command="commands", description="📋 Список всех команд"),
            BotCommand(command="lang", description="🌐 Сменить язык"),
            BotCommand(command="help", description="📖 Помощь и правила"),
        ],
        "group": [
            BotCommand(command="game", description="🎮 Создать игру Мафия"),
            BotCommand(command="start", description="🚀 Начать досрочно"),
            BotCommand(command="extend", description="⏳ Продлить набор (+30с)"),
            BotCommand(command="roles", description="🎭 Описание ролей"),
            BotCommand(command="stop", description="🛑 Остановить игру"),
            BotCommand(command="setlang", description="🌐 Язык группы"),
            BotCommand(command="help", description="📖 Команды группы"),
        ]
    },
    "en": {
        "private": [
            BotCommand(command="profile", description="👤 Profile & balance"),
            BotCommand(command="shop", description="🛒 Store (Cards, fake docs)"),
            BotCommand(command="daily", description="🎁 Daily coin bonus"),
            BotCommand(command="roulette", description="🎰 Lucky Wheel (Roulette)"),
            BotCommand(command="tournament", description="🏆 Tournaments & prizes"),
            BotCommand(command="clan", description="🛡 Mafia Clan"),
            BotCommand(command="top", description="📊 Leaderboard"),
            BotCommand(command="roles", description="🎭 All game roles & powers"),
            BotCommand(command="commands", description="📋 All commands"),
            BotCommand(command="lang", description="🌐 Change language"),
            BotCommand(command="help", description="📖 Help & game rules"),
        ],
        "group": [
            BotCommand(command="game", description="🎮 Create new Mafia game"),
            BotCommand(command="start", description="🚀 Start game early"),
            BotCommand(command="extend", description="⏳ Extend lobby time (+30s)"),
            BotCommand(command="roles", description="🎭 Role descriptions"),
            BotCommand(command="stop", description="🛑 Cancel game (Admin)"),
            BotCommand(command="setlang", description="🌐 Group language"),
            BotCommand(command="help", description="📖 Group commands & help"),
        ]
    },
    "tr": {
        "private": [
            BotCommand(command="profile", description="👤 Profil ve bakiye"),
            BotCommand(command="shop", description="🛒 Mağaza (Kartlar, sahte kimlik)"),
            BotCommand(command="daily", description="🎁 Günlük altın ödülü"),
            BotCommand(command="roulette", description="🎰 Çarkıfelek (Rulet)"),
            BotCommand(command="tournament", description="🏆 Turnuvalar ve ödüller"),
            BotCommand(command="clan", description="🛡 Mafya Klanı"),
            BotCommand(command="top", description="📊 Liderlik tablosu"),
            BotCommand(command="roles", description="🎭 Oyundaki tüm roller"),
            BotCommand(command="commands", description="📋 Tüm komutlar"),
            BotCommand(command="lang", description="🌐 Dil seçimi"),
            BotCommand(command="help", description="📖 Yardım ve kurallar"),
        ],
        "group": [
            BotCommand(command="game", description="🎮 Yeni Mafya oyunu başlat"),
            BotCommand(command="start", description="🚀 Erken başlat"),
            BotCommand(command="extend", description="⏳ Süreyi uzat (+30sn)"),
            BotCommand(command="roles", description="🎭 Rol açıklamaları"),
            BotCommand(command="stop", description="🛑 Oyunu durdur (Yönetici)"),
            BotCommand(command="setlang", description="🌐 Grup dilini ayarla"),
            BotCommand(command="help", description="📖 Grup komutları"),
        ]
    }
}

async def setup_bot_commands(bot: Bot):
    try:
        # 1. Register default commands (Uzbek)
        uz_cmds = COMMANDS_BY_LANG["uz"]
        await bot.set_my_commands(uz_cmds["private"], scope=BotCommandScopeDefault())
        await bot.set_my_commands(uz_cmds["group"], scope=BotCommandScopeAllGroupChats())

        # 2. Register per-language commands for Telegram clients
        for lang_code, cmds in COMMANDS_BY_LANG.items():
            try:
                await bot.set_my_commands(cmds["private"], scope=BotCommandScopeDefault(), language_code=lang_code)
                await bot.set_my_commands(cmds["group"], scope=BotCommandScopeAllGroupChats(), language_code=lang_code)
            except Exception as e:
                logger.warning(f"Could not set commands for {lang_code}: {e}")

        logger.info("Telegram Bot Menu commands successfully configured in all languages (Default: Uzbek)!")
    except Exception as e:
        logger.warning(f"Failed to set bot commands: {e}")

async def main():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Please provide a valid BOT_TOKEN in your .env file or environment!")
        sys.exit(1)

    # Initialize SQLite / PostgreSQL tables
    logger.info("Initializing database tables...")
    await init_db()

    # Optional HTTP server for Render Web Service port check
    web_runner = None
    port = os.getenv("PORT")
    if port:
        web_runner = await start_web_server(int(port))

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
    dp.include_router(admin_router)
    dp.include_router(roulette_router)
    dp.include_router(roles_router)

    logger.info(f"Starting {settings.BOT_NAME} (@{settings.BOT_USERNAME}) polling...")
    try:
        await setup_bot_commands(bot)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
