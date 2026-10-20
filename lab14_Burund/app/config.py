from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки берутся из переменных окружения или файла .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://hotel:hotel@localhost:5432/hotel"
    redis_url: str | None = "redis://localhost:6379/0"
    cache_ttl: int = 120
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
