import os
from datetime import timedelta

from superapp_shared import env_bool, env_list


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8080"))
    DB_URL: str = os.getenv(
        "DB_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5433/payments",
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me_in_prod")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")  # HS256|RS256
    JWT_KEY_ID: str = os.getenv("JWT_KEY_ID", "kid-dev")
    JWT_RS_PRIVATE_PEM: str | None = os.getenv("JWT_RS_PRIVATE_PEM")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )
    AUTO_CREATE_SCHEMA: bool = env_bool("AUTO_CREATE_SCHEMA", default=DEV_MODE)
    DEV_ENABLE_TOPUP: bool = env_bool("DEV_ENABLE_TOPUP", default=DEV_MODE)
    DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "SYP")
    QR_EXPIRY_MINUTES: int = int(os.getenv("QR_EXPIRY_MINUTES", "15"))
    REQUEST_EXPIRY_MINUTES: int = int(os.getenv("REQUEST_EXPIRY_MINUTES", "30"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")  # memory|redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl")
    # OTP settings
    OTP_MODE: str = os.getenv("OTP_MODE", "dev")  # dev|redis
    OTP_TTL_SECS: int = int(os.getenv("OTP_TTL_SECS", "300"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    DEV_DISABLE_OTP: bool = env_bool("DEV_DISABLE_OTP", default=False)
    DEV_RESET_USER_STATE_ON_LOGIN: bool = env_bool(
        "DEV_RESET_USER_STATE_ON_LOGIN",
        default=DEV_MODE,
    )
    # JWT claims and validation
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "payments")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "users")
    JWT_VALIDATE_ISS: bool = env_bool("JWT_VALIDATE_ISS", default=False)
    JWT_VALIDATE_AUD: bool = env_bool("JWT_VALIDATE_AUD", default=False)
    JWT_CLOCK_SKEW_SECS: int = int(os.getenv("JWT_CLOCK_SKEW_SECS", "0"))
    # Internal API signing
    INTERNAL_REQUIRE_HMAC: bool = env_bool("INTERNAL_REQUIRE_HMAC", default=True)
    INTERNAL_HMAC_TTL_SECS: int = int(os.getenv("INTERNAL_HMAC_TTL_SECS", "300"))
    # KYC policy (cents)
    KYC_L0_TX_MAX_CENTS: int = int(os.getenv("KYC_L0_TX_MAX_CENTS", "100000000"))  # 1,000,000.00 SYP
    KYC_L0_DAILY_MAX_CENTS: int = int(os.getenv("KYC_L0_DAILY_MAX_CENTS", "500000000"))
    KYC_L1_TX_MAX_CENTS: int = int(os.getenv("KYC_L1_TX_MAX_CENTS", "500000000"))
    KYC_L1_DAILY_MAX_CENTS: int = int(os.getenv("KYC_L1_DAILY_MAX_CENTS", "2000000000"))
    KYC_MIN_LEVEL_FOR_MERCHANT_PAY: int = int(os.getenv("KYC_MIN_LEVEL_FOR_MERCHANT_PAY", "1"))
    KYC_MIN_LEVEL_FOR_MERCHANT_QR: int = int(os.getenv("KYC_MIN_LEVEL_FOR_MERCHANT_QR", "1"))
    # Fees
    FEE_WALLET_PHONE: str = os.getenv("FEE_WALLET_PHONE", "+963999999999")
    MERCHANT_FEE_BPS: int = int(os.getenv("MERCHANT_FEE_BPS", "0"))
    CASHIN_FEE_BPS: int = int(os.getenv("CASHIN_FEE_BPS", "0"))
    CASHOUT_FEE_BPS: int = int(os.getenv("CASHOUT_FEE_BPS", "0"))
    # Voucher cash top-up fee (in basis points)
    VOUCHER_FEE_BPS: int = int(os.getenv("VOUCHER_FEE_BPS", "100"))  # default 1%
    INTERNAL_API_SECRET: str = os.getenv("INTERNAL_API_SECRET", "dev_secret")
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "")
    ADMIN_TOKEN_SHA256: str = os.getenv("ADMIN_TOKEN_SHA256", "")
    # Starting credit (in cents). Applied on first wallet creation; can be
    # backfilled to existing users via admin endpoint. Set to 0 to disable.
    STARTING_CREDIT_CENTS: int = int(
        os.getenv("STARTING_CREDIT_CENTS", "10000000" if DEV_MODE else "0")
    )  # 100,000 SYP in dev, off otherwise
    # Passkeys (WebAuthn) — dev scaffolding
    PASSKEYS_ENABLED: bool = env_bool("PASSKEYS_ENABLED", default=True)
    PASSKEYS_DEV_UNSAFE: bool = env_bool("PASSKEYS_DEV_UNSAFE", default=True)
    PASSKEYS_RP_ID: str = os.getenv("PASSKEYS_RP_ID", "localhost")
    PASSKEYS_RP_NAME: str = os.getenv("PASSKEYS_RP_NAME", "SuperApp")
    PASSKEYS_ORIGIN: str = os.getenv("PASSKEYS_ORIGIN", "http://localhost")

    # Controlled backdoor OTP for field testing (explicitly opt-in via env)
    BACKDOOR_PHONE: str = os.getenv("BACKDOOR_PHONE", "").strip()
    BACKDOOR_OTP: str = os.getenv("BACKDOOR_OTP", "").strip()

    @property
    def jwt_expires_delta(self) -> timedelta:
        return timedelta(minutes=self.JWT_EXPIRES_MINUTES)

    @property
    def admin_token_hashes(self) -> list[str]:
        raw = (os.getenv("ADMIN_TOKEN_SHA256", getattr(self, "ADMIN_TOKEN_SHA256", "")) or "").split(',')
        return [r.strip().lower() for r in raw if r.strip()]


settings = Settings()
 
# Harden secrets for non-dev environments
if not settings.DEV_MODE:
    if not settings.JWT_SECRET or settings.JWT_SECRET == "change_me_in_prod":
        raise RuntimeError("JWT_SECRET must be set securely when ENV!=dev")
    if not settings.INTERNAL_API_SECRET or settings.INTERNAL_API_SECRET == "dev_secret":
        raise RuntimeError("INTERNAL_API_SECRET must be set securely when ENV!=dev")
    if not settings.ADMIN_TOKEN and not settings.admin_token_hashes:
        raise RuntimeError("Provide ADMIN_TOKEN or ADMIN_TOKEN_SHA256 when ENV!=dev")
    if not settings.ALLOWED_ORIGINS or "*" in settings.ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS must list explicit origins when ENV!=dev")
    if settings.AUTO_CREATE_SCHEMA:
        raise RuntimeError("AUTO_CREATE_SCHEMA cannot be enabled when ENV!=dev")
    if settings.DEV_ENABLE_TOPUP:
        raise RuntimeError("DEV_ENABLE_TOPUP must be false when ENV!=dev")
    if settings.DEV_RESET_USER_STATE_ON_LOGIN:
        raise RuntimeError("DEV_RESET_USER_STATE_ON_LOGIN must be false when ENV!=dev")
    if settings.OTP_MODE == "dev":
        raise RuntimeError("OTP_MODE=dev is not permitted when ENV!=dev")
    if getattr(settings, "RATE_LIMIT_BACKEND", "memory").lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
