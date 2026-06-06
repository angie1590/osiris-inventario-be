from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "production", "test"] = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://osiris:osiris_dev_pass@localhost:5432/osiris_inventario"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Inventory
    KARDEX_METHOD: Literal["PEPS", "WEIGHTED_AVERAGE"] = "PEPS"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Audit
    MAX_EXPORT_DATE_RANGE_DAYS: int = 90
    APP_TIMEZONE: str = "America/Guayaquil"


settings = Settings()
