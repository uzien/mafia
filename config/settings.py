from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    ADMIN_IDS: List[int] = []
    
    # Database
    DB_URL: str = "sqlite+aiosqlite:///mafia_bot.db"
    
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
