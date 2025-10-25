import os
from superapp_shared import env_bool, env_list


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8099"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )

    # Providers
    PROVIDER: str = os.getenv("AI_PROVIDER", "local")
    PROVIDER_BASE_URL: str = os.getenv("AI_PROVIDER_BASE_URL", "")
    PROVIDER_API_KEY: str = os.getenv("AI_PROVIDER_API_KEY", "")

    # Limits & Safety
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl_ai_gw")

    # Downstream service endpoints
    UTILITIES_BASE_URL: str = os.getenv("UTILITIES_BASE_URL", "http://localhost:8084")
    INTERNAL_API_SECRET: str = os.getenv("INTERNAL_API_SECRET", "dev_ai_secret")
    PARKING_ONSTREET_BASE_URL: str = os.getenv("PARKING_ONSTREET_BASE_URL", "http://localhost:8096")
    CARMARKET_BASE_URL: str = os.getenv("CARMARKET_BASE_URL", "http://localhost:8086")
    CHAT_BASE_URL: str = os.getenv("CHAT_BASE_URL", "http://localhost:8091")


settings = Settings()

if not settings.DEV_MODE:
    if not settings.ALLOWED_ORIGINS or "*" in settings.ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS must be explicit when ENV!=dev")
    # Rate limiter must be redis in prod
    if getattr(settings, "RATE_LIMIT_BACKEND", "memory").lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
    if not settings.REDIS_URL or not settings.REDIS_URL.startswith("redis://"):
        raise RuntimeError("REDIS_URL must be set to a redis:// URL when ENV!=dev")
