import os
from datetime import timedelta

from superapp_shared import env_bool, env_list


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8093"))
    DB_URL: str = os.getenv(
        "DB_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5445/agriculture",
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me_in_prod")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )
    AUTO_CREATE_SCHEMA: bool = env_bool("AUTO_CREATE_SCHEMA", default=DEV_MODE)

    # Rate limiting
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl_agri")

    # OTP
    OTP_MODE: str = os.getenv("OTP_MODE", "dev")
    OTP_TTL_SECS: int = int(os.getenv("OTP_TTL_SECS", "300"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    DEV_DISABLE_OTP: bool = env_bool("DEV_DISABLE_OTP", default=False)

    # Notifications
    NOTIFY_MODE: str = os.getenv("NOTIFY_MODE", "log")  # log|redis
    NOTIFY_REDIS_CHANNEL: str = os.getenv("NOTIFY_REDIS_CHANNEL", "agriculture.events")

    # Payments (optional)
    PAYMENTS_BASE_URL: str = os.getenv("PAYMENTS_BASE_URL", "")
    PAYMENTS_INTERNAL_SECRET: str = os.getenv("PAYMENTS_INTERNAL_SECRET", "")
    FEE_WALLET_PHONE: str = os.getenv("FEE_WALLET_PHONE", "+963000000000")
    PAYMENTS_WEBHOOK_SECRET: str = os.getenv("PAYMENTS_WEBHOOK_SECRET", "")

    @property
    def jwt_expires_delta(self) -> timedelta:
        return timedelta(minutes=self.JWT_EXPIRES_MINUTES)


settings = Settings()

# Harden secrets for non-dev environments
if not settings.DEV_MODE:
    if not settings.ALLOWED_ORIGINS or "*" in settings.ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS must list explicit origins when ENV!=dev")
    if settings.AUTO_CREATE_SCHEMA:
        raise RuntimeError("AUTO_CREATE_SCHEMA cannot be enabled when ENV!=dev")
    if getattr(settings, "OTP_MODE", None) == "dev":
        raise RuntimeError("OTP_MODE=dev is not permitted when ENV!=dev")
    if not settings.JWT_SECRET or settings.JWT_SECRET == "change_me_in_prod":
        raise RuntimeError("JWT_SECRET must be set securely when ENV!=dev")
    # Rate limiter must be redis in prod
    if getattr(settings, "RATE_LIMIT_BACKEND", "memory").lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
    if not settings.REDIS_URL or not settings.REDIS_URL.startswith("redis://"):
        raise RuntimeError("REDIS_URL must be set to a redis:// URL when ENV!=dev")
