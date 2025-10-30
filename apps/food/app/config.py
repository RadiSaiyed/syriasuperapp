import os
from datetime import timedelta

from superapp_shared import env_bool, env_list


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8090"))
    DB_URL: str = os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5443/food")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me_in_prod")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )
    AUTO_CREATE_SCHEMA: bool = env_bool("AUTO_CREATE_SCHEMA", default=DEV_MODE)
    # Payments
    PAYMENTS_BASE_URL: str = os.getenv("PAYMENTS_BASE_URL", "http://host.docker.internal:8080")
    PAYMENTS_INTERNAL_SECRET: str = os.getenv("PAYMENTS_INTERNAL_SECRET", "dev_secret")
    PAYMENTS_WEBHOOK_SECRET: str = os.getenv("PAYMENTS_WEBHOOK_SECRET", "")
    PLATFORM_FEE_BPS: int = int(os.getenv("PLATFORM_FEE_BPS", "0"))
    FEE_WALLET_PHONE: str = os.getenv("FEE_WALLET_PHONE", "+963999999999")
    # Rate limiting
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl_food")
    # Notifications + Webhooks
    NOTIFY_MODE: str = os.getenv("NOTIFY_MODE", "log")  # log|redis
    NOTIFY_REDIS_CHANNEL: str = os.getenv("NOTIFY_REDIS_CHANNEL", "food.events")
    WEBHOOK_ENABLED: str = os.getenv("WEBHOOK_ENABLED", "false")
    WEBHOOK_TIMEOUT_SECS: int = int(os.getenv("WEBHOOK_TIMEOUT_SECS", "3"))
    WEBHOOK_MAX_ATTEMPTS: int = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "5"))
    WEBHOOK_WORKER_INTERVAL_SECS: int = int(os.getenv("WEBHOOK_WORKER_INTERVAL_SECS", "10"))
    # OTP
    OTP_MODE: str = os.getenv("OTP_MODE", "dev")
    OTP_TTL_SECS: int = int(os.getenv("OTP_TTL_SECS", "300"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    DEV_DISABLE_OTP: bool = env_bool("DEV_DISABLE_OTP", default=False)
    # Inventory / Pricing
    STOCK_LOW_THRESHOLD: int = int(os.getenv("STOCK_LOW_THRESHOLD", "3"))
    # Payout taxes/fees
    TAX_RATE_BPS: int = int(os.getenv("TAX_RATE_BPS", "0"))
    # Optional TOTP 2FA (applies where service enables it)
    REQUIRE_TOTP: bool = env_bool("REQUIRE_TOTP", default=False)
    # ESC/POS (best effort)
    ESCPOS_DEVICE: str = os.getenv("ESCPOS_DEVICE", "")

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
    if not settings.PAYMENTS_INTERNAL_SECRET or settings.PAYMENTS_INTERNAL_SECRET == "dev_secret":
        raise RuntimeError("PAYMENTS_INTERNAL_SECRET must be set securely when ENV!=dev")
    if settings.WEBHOOK_ENABLED.lower() == "true" and not settings.PAYMENTS_WEBHOOK_SECRET:
        raise RuntimeError("PAYMENTS_WEBHOOK_SECRET must be set when webhooks enabled and ENV!=dev")
    if getattr(settings, "RATE_LIMIT_BACKEND", "memory").lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
