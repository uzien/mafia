from typing import Any, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    BOT_NAME: str = "Mafia Litsey Bot"
    BOT_USERNAME: str = "Mafia_litsey_bot"
    ADMIN_IDS_RAW: Any = Field(default=[], validation_alias="ADMIN_IDS")

    @property
    def ADMIN_IDS(self) -> List[int]:
        v = self.ADMIN_IDS_RAW
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return [int(x) for x in json.loads(v)]
                except Exception:
                    pass
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts if p.isdigit() or (p.startswith("-") and p[1:].isdigit())]
        if isinstance(v, (list, set, tuple)):
            return [int(x) for x in v]
        return []
    
    # Database
    DB_URL: str = "sqlite+aiosqlite:///mafia_bot.db"
    DATABASE_URL: str = ""

    @property
    def async_db_url(self) -> str:
        url = (self.DATABASE_URL or "").strip().strip("'\"")
        if not url:
            url = self.DB_URL
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url
    
    # Game Settings
    MIN_PLAYERS: int = 4
    MAX_PLAYERS: int = 20
    LOBBY_TIMEOUT: int = 60         # Seconds for lobby wait
    NIGHT_DURATION: int = 45        # Seconds for night actions
    DAY_DURATION: int = 60          # Seconds for open discussion
    VOTING_DURATION: int = 45       # Seconds for daytime lynching vote
    DEFENSE_DURATION: int = 20      # Seconds for accused player's final speech
    
    # Default Language (az, uz, ru, en, tr)
    DEFAULT_LANGUAGE: str = "az"
    
    # Economy Rewards
    WIN_COIN_REWARD: int = 150
    LOSE_COIN_REWARD: int = 30
    WIN_EXP_REWARD: int = 100
    LOSE_EXP_REWARD: int = 25
    DAILY_BONUS_MIN: int = 50
    DAILY_BONUS_MAX: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
