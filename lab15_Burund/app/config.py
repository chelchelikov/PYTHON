import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DATABASE_URL = os.getenv("DATABASE_URL",
                             "postgresql+psycopg://restaurant:restaurant@localhost:5432/restaurant_web")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    TESTING = False


class TestConfig(Config):
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    TESTING = True
    LOG_LEVEL = "WARNING"
