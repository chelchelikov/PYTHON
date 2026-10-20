import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    db_path: str = os.getenv("DB_PATH", "hotel_bot.db")
    admin_ids: frozenset[int] = field(default_factory=lambda: frozenset(
        int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


def load_config() -> Config:
    return Config()
