"""Configuration management for Zone Weaver backend."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # Environment variables always take precedence over .env file values,
        # which ensures the Railway-provided DATABASE_URL is used in production.
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/zoneweaver"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production-minimum-32-chars-required"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # API
    API_TITLE: str = "Zone Weaver API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "User-Defined Zone Message Distribution Platform"

    # H3
    H3_DEFAULT_RESOLUTION: int = 13
    H3_MIN_RESOLUTION: int = 0
    H3_MAX_RESOLUTION: int = 15

    # Account
    MAX_ZONES_PER_USER: int = 3

    # Geocoding (placeholder for future integration)
    GEOCODING_PROVIDER: str = "nominatim"


settings = Settings()
