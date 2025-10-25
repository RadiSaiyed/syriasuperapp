import os
from datetime import timedelta

from superapp_shared import env_bool, env_list


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8092"))
    DB_URL: str = os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5436/realestate")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev_secret_realestate")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )
    AUTO_CREATE_SCHEMA: bool = env_bool("AUTO_CREATE_SCHEMA", default=DEV_MODE)
    OTP_MODE: str = os.getenv("OTP_MODE", "dev")
    # Rate limiting
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl_realestate")
    # Payments integration (internal dev endpoints)
    PAYMENTS_BASE_URL: str = os.getenv("PAYMENTS_BASE_URL", "http://host.docker.internal:8080")
    PAYMENTS_INTERNAL_SECRET: str = os.getenv("PAYMENTS_INTERNAL_SECRET", "dev_secret")
    FEE_WALLET_PHONE: str = os.getenv("FEE_WALLET_PHONE", "+963999999999")
    RESERVATION_FEE_CENTS: int = int(os.getenv("RESERVATION_FEE_CENTS", "500000"))  # 5,000 SYP

    @property
    def jwt_delta(self) -> timedelta:
        return timedelta(minutes=self.JWT_EXPIRES_MINUTES)


settings = Settings()

if not settings.DEV_MODE:
    if not settings.ALLOWED_ORIGINS or "*" in settings.ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS must list explicit origins when ENV!=dev")
    if settings.AUTO_CREATE_SCHEMA:
        raise RuntimeError("AUTO_CREATE_SCHEMA cannot be enabled when ENV!=dev")
    if getattr(settings, "OTP_MODE", None) == "dev":
        raise RuntimeError("OTP_MODE=dev is not permitted when ENV!=dev")
    if not settings.JWT_SECRET or settings.JWT_SECRET == "dev_secret_realestate":
        raise RuntimeError("JWT_SECRET must be set securely when ENV!=dev")
    if not settings.PAYMENTS_INTERNAL_SECRET or settings.PAYMENTS_INTERNAL_SECRET == "dev_secret":
        raise RuntimeError("PAYMENTS_INTERNAL_SECRET must be set securely when ENV!=dev")
    # Rate limiter must be redis in prod
    if getattr(settings, "RATE_LIMIT_BACKEND", "memory").lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
    if not settings.REDIS_URL or not settings.REDIS_URL.startswith("redis://"):
        raise RuntimeError("REDIS_URL must be set to a redis:// URL when ENV!=dev")
