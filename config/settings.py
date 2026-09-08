from typing import Any, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    BOT_NAME: str = "Mafia Litsey Bot"
    BOT_USERNAME: str = "Mafia_litsey_bot"
    MAIN_GROUP_USERNAME: str = "mafia_adu_litsey"
    MAIN_GROUP_URL: str = "https://t.me/mafia_adu_litsey"
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
        import urllib.parse
        raw = (self.DATABASE_URL or "").strip().strip("'\"")
        if not raw:
            return self.DB_URL
        
        prefix = ""
        for p in ["postgresql+asyncpg://", "postgresql://", "postgres://"]:
            if raw.startswith(p):
                prefix = p
                break
        
        if not prefix:
            return raw
            
        remainder = raw[len(prefix):]
        # Handle unencoded special characters in credentials if present
        if "@" in remainder:
            auth_part, host_part = remainder.rsplit("@", 1)
            if ":" in auth_part:
                user, password = auth_part.split(":", 1)
                user = urllib.parse.quote(urllib.parse.unquote(user), safe="")
                password = urllib.parse.quote(urllib.parse.unquote(password), safe="")
                auth_part = f"{user}:{password}"
            remainder = f"{auth_part}@{host_part}"
        
        # If connecting to render.com external host without ssl query, append ?ssl=require
        if ".render.com" in remainder and "ssl" not in remainder:
            delimiter = "&" if "?" in remainder else "?"
            remainder = f"{remainder}{delimiter}ssl=require"
            
        return f"postgresql+asyncpg://{remainder}"
    
    # Game Settings
    MIN_PLAYERS: int = 4
    MAX_PLAYERS: int = 20
    LOBBY_TIMEOUT: int = 60         # Seconds for lobby wait
    NIGHT_DURATION: int = 45        # Seconds for night actions
    DAY_DURATION: int = 60          # Seconds for open discussion
    VOTING_DURATION: int = 45       # Seconds for daytime lynching vote
    DEFENSE_DURATION: int = 20      # Seconds for accused player's final speech
    
    # Default Language (uz, az, ru, en, tr)
    DEFAULT_LANGUAGE: str = "uz"
    
    # Economy Rewards
    WIN_COIN_REWARD: int = 150
    LOSE_COIN_REWARD: int = 30
    WIN_EXP_REWARD: int = 100
    LOSE_EXP_REWARD: int = 25
    DAILY_BONUS_MIN: int = 50
    DAILY_BONUS_MAX: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
