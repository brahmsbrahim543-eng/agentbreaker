import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    DATABASE_URL: str = "sqlite+aiosqlite:///./agentbreaker.db"
    REDIS_URL: str = ""
    SECRET_KEY: str = secrets.token_urlsafe(64)

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://agentbreaker.com",
        "https://www.agentbreaker.com",
        "https://app.agentbreaker.com",
        "https://agentbreaker-web.onrender.com",
    ]
    API_VERSION: str = "v1"

    RATE_LIMIT_PER_MINUTE: int = 100
    DEFAULT_KILL_THRESHOLD: int = 75
    DEFAULT_CARBON_REGION: str = "us-east"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    SIMULATOR_ENABLED: bool = False
    GOOGLE_API_KEY: str = ""

    # Stripe billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_STARTER_PRICE_ID: str = ""
    STRIPE_GROWTH_PRICE_ID: str = ""
    STRIPE_ENTERPRISE_PRICE_ID: str = ""

    # App URLs
    APP_URL: str = "https://app.agentbreaker.com"
    API_URL: str = "https://api.agentbreaker.com"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
