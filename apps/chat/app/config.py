import os
from datetime import timedelta

try:
    from superapp_shared.env import env_bool, env_list  # type: ignore
except Exception:
    from superapp_shared import env_bool, env_list  # type: ignore


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8091"))
    DB_URL: str = os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5444/chat")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me_in_prod")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )
    AUTO_CREATE_SCHEMA: bool = env_bool("AUTO_CREATE_SCHEMA", default=DEV_MODE)
    # Rate limiting
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl_chat")
    # OTP
    OTP_MODE: str = os.getenv("OTP_MODE", "dev")
    OTP_TTL_SECS: int = int(os.getenv("OTP_TTL_SECS", "300"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    DEV_DISABLE_OTP: bool = env_bool("DEV_DISABLE_OTP", default=False)
    # Events/Webhooks
    NOTIFY_MODE: str = os.getenv("NOTIFY_MODE", "log")
    NOTIFY_REDIS_CHANNEL: str = os.getenv("NOTIFY_REDIS_CHANNEL", "chat.events")
    WEBHOOK_ENABLED: str = os.getenv("WEBHOOK_ENABLED", "false")
    WEBHOOK_TIMEOUT_SECS: int = int(os.getenv("WEBHOOK_TIMEOUT_SECS", "3"))
    # Payments (optional)
    PAYMENTS_BASE_URL: str = os.getenv("PAYMENTS_BASE_URL", "")
    PAYMENTS_INTERNAL_SECRET: str = os.getenv("PAYMENTS_INTERNAL_SECRET", "")
    PAYMENTS_WEBHOOK_SECRET: str = os.getenv("PAYMENTS_WEBHOOK_SECRET", "")
    # Internal API
    INTERNAL_API_SECRET: str = os.getenv("INTERNAL_API_SECRET", "dev_ai_secret")
    # Push
    PUSH_PROVIDER: str = os.getenv("PUSH_PROVIDER", "none")  # none|fcm|apns
    FCM_SERVER_KEY: str = os.getenv("FCM_SERVER_KEY", "")
    # Quotas
    CHAT_USER_MSGS_PER_MINUTE: int = int(os.getenv("CHAT_USER_MSGS_PER_MINUTE", "60"))
    CHAT_GROUP_MSGS_PER_MINUTE: int = int(os.getenv("CHAT_GROUP_MSGS_PER_MINUTE", "120"))
    CHAT_PUBLIC_BASE_URL: str = os.getenv("CHAT_PUBLIC_BASE_URL", "https://superapp.local")

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
    if getattr(settings, "RATE_LIMIT_BACKEND", "memory").lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
