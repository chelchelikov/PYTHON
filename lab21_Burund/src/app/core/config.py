from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения (или файла .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Restaurant Delivery"
    database_url: str = "sqlite:///./restaurant.db"
    redis_url: str | None = None
    broker_url: str | None = None
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60
    admin_email: str = "admin@restaurant.ru"
    admin_password: str = "admin12345"
    menu_cache_ttl: int = 60
    seed_demo_data: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
