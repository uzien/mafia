import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import settings
from database.models import Base

logger = logging.getLogger("mafia_bot.db")

class DynamicSessionManager:
    def __init__(self, initial_url: str):
        self.url = initial_url
        self.engine = create_async_engine(self.url, echo=False)
        self._maker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    def switch_engine(self, new_url: str):
        self.url = new_url
        self.engine = create_async_engine(self.url, echo=False)
        self._maker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    def __call__(self, **kwargs) -> AsyncSession:
        return self._maker(**kwargs)

session_manager = DynamicSessionManager(settings.async_db_url)
async_session_maker = session_manager
engine = session_manager.engine

async def init_db():
    global engine
    target_url = session_manager.url
    is_postgres = "postgresql" in target_url

    if is_postgres:
        from sqlalchemy.engine.url import make_url
        try:
            parsed = make_url(target_url)
            logger.info(f"Database target: {parsed.render_as_string(hide_password=True)}")
        except Exception:
            pass

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Connecting to PostgreSQL (attempt {attempt}/{max_retries})...")
                async with session_manager.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                logger.info("✅ Successfully connected to PostgreSQL and initialized tables!")
                return
            except Exception as e:
                logger.warning(f"PostgreSQL connection attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                else:
                    logger.error(
                        "\n====================================================================\n"
                        f"❌ FAILED TO CONNECT TO POSTGRESQL DATABASE: {e}\n\n"
                        "Common causes on Render:\n"
                        "1. Region Mismatch: If your Web Service and PostgreSQL are in different regions,\n"
                        "   the internal host (e.g. dpg-xxxx-a) cannot resolve. Use the External Database URL!\n"
                        "2. Hostname typo / Incomplete copy in Render environment variables.\n"
                        "3. Database still provisioning or suspended.\n\n"
                        "👉 RESILIENT FALLBACK: Switching to local SQLite database (mafia_bot.db)\n"
                        "so the bot stays online and operational without crashing!\n"
                        "===================================================================="
                    )
                    fallback_url = "sqlite+aiosqlite:///mafia_bot.db"
                    session_manager.switch_engine(fallback_url)
                    engine = session_manager.engine
                    async with session_manager.engine.begin() as conn:
                        await conn.run_sync(Base.metadata.create_all)
                    logger.info("✅ SQLite fallback database initialized successfully!")
                    return
    else:
        async with session_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ SQLite database initialized successfully!")

async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
