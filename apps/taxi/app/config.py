import os
from datetime import timedelta

from superapp_shared import env_bool, env_list


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8081"))
    DB_URL: str = os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me_in_prod")
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "43200"))
    ALLOWED_ORIGINS: list[str] = env_list(
        "ALLOWED_ORIGINS",
        default=["*"] if DEV_MODE else [],
    )
    AUTO_CREATE_SCHEMA: bool = env_bool("AUTO_CREATE_SCHEMA", default=DEV_MODE)
    BASE_FARE_CENTS: int = int(os.getenv("BASE_FARE_CENTS", "4000"))
    PER_KM_CENTS: int = int(os.getenv("PER_KM_CENTS", "7500"))
    LOYALTY_RIDE_INTERVAL: int = int(os.getenv("LOYALTY_RIDE_INTERVAL", "10"))
    LOYALTY_RIDER_FREE_CAP_CENTS: int = int(os.getenv("LOYALTY_RIDER_FREE_CAP_CENTS", "50000"))
    TRAFFIC_BASE_PACE_MIN_PER_KM: float = float(os.getenv("TRAFFIC_BASE_PACE_MIN_PER_KM", "2.0"))
    TRAFFIC_SURCHARGE_PER_MIN_CENTS: int = int(os.getenv("TRAFFIC_SURCHARGE_PER_MIN_CENTS", "1000"))
    TRAFFIC_SURCHARGE_MAX_MULTIPLIER: float = float(os.getenv("TRAFFIC_SURCHARGE_MAX_MULTIPLIER", "3.0"))
    ASSIGN_RADIUS_KM: float = float(os.getenv("ASSIGN_RADIUS_KM", "5"))
    PAYMENTS_BASE_URL: str = os.getenv("PAYMENTS_BASE_URL", "http://host.docker.internal:8080")
    PAYMENTS_INTERNAL_SECRET: str = os.getenv("PAYMENTS_INTERNAL_SECRET", "dev_secret")
    PLATFORM_FEE_BPS: int = int(os.getenv("PLATFORM_FEE_BPS", "1000"))
    FEE_WALLET_PHONE: str = os.getenv("FEE_WALLET_PHONE", "+963999999999")
    PAYMENTS_WALLET_CACHE_SECS: int = int(os.getenv("PAYMENTS_WALLET_CACHE_SECS", "30"))
    # Payments Circuit Breaker
    PAYMENTS_CB_ENABLED: bool = os.getenv("PAYMENTS_CB_ENABLED", "false").lower() == "true"
    PAYMENTS_CB_THRESHOLD: int = int(os.getenv("PAYMENTS_CB_THRESHOLD", "3"))
    PAYMENTS_CB_COOLDOWN_SECS: int = int(os.getenv("PAYMENTS_CB_COOLDOWN_SECS", "60"))
    # Taxi Wallet
    TAXI_WALLET_ENABLED: bool = os.getenv("TAXI_WALLET_ENABLED", "true").lower() == "true"
    TAXI_POOL_WALLET_PHONE = os.getenv("TAXI_POOL_WALLET_PHONE", None)
    TAXI_ESCROW_WALLET_PHONE = os.getenv("TAXI_ESCROW_WALLET_PHONE", None)
    # Pricing/ETA
    AVG_SPEED_KMPH: float = float(os.getenv("AVG_SPEED_KMPH", "30"))
    SURGE_AVAILABLE_THRESHOLD: int = int(os.getenv("SURGE_AVAILABLE_THRESHOLD", "3"))
    SURGE_STEP_PER_MISSING: float = float(os.getenv("SURGE_STEP_PER_MISSING", "0.25"))
    SURGE_MAX_MULTIPLIER: float = float(os.getenv("SURGE_MAX_MULTIPLIER", "2.0"))
    # Maps provider (Google Maps)
    MAPS_INCLUDE_POLYLINE: bool = os.getenv("MAPS_INCLUDE_POLYLINE", "true").lower() == "true"
    GOOGLE_MAPS_BASE_URL: str = os.getenv("GOOGLE_MAPS_BASE_URL", "https://maps.googleapis.com")
    GOOGLE_MAPS_API_KEY: str | None = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY_TAXI")
    GOOGLE_USE_TRAFFIC: bool = os.getenv("GOOGLE_USE_TRAFFIC", "true").lower() == "true"
    MAPS_TIMEOUT_SECS: float = float(os.getenv("MAPS_TIMEOUT_SECS", os.getenv("GOOGLE_TIMEOUT_SECS", "5.0")))
    MAPS_MAX_RETRIES: int = int(os.getenv("MAPS_MAX_RETRIES", os.getenv("GOOGLE_MAX_RETRIES", "2")))
    MAPS_BACKOFF_SECS: float = float(os.getenv("MAPS_BACKOFF_SECS", os.getenv("GOOGLE_BACKOFF_SECS", "0.25")))
    MAPS_GEOCODER_CACHE_SECS: int = int(os.getenv("MAPS_GEOCODER_CACHE_SECS", "120"))
    # Ride classes: price multipliers (e.g. "standard=1.0,comfort=1.1,yellow=1.0,vip=1.5,van=1.4,electro=0.95")
    RIDE_CLASS_MULTIPLIERS_RAW: str = os.getenv(
        "RIDE_CLASS_MULTIPLIERS",
        "standard=1.0,comfort=1.1,yellow=1.0,vip=1.5,van=1.4,electro=0.95",
    )

    def _parse_class_map(self, raw: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for part in (raw or "").split(','):
            part = part.strip()
            if not part:
                continue
            if '=' in part:
                k, v = part.split('=', 1)
                k = k.strip().lower()
                try:
                    out[k] = float(v.strip())
                except Exception:
                    continue
        if not out:
            # Fallback default mapping
            out = {
                'standard': 1.0,
                'comfort': 1.1,
                'yellow': 1.0,
                'vip': 1.5,
                'van': 1.4,
                'electro': 0.95,
            }
        return out

    @property
    def RIDE_CLASS_MULTIPLIERS(self) -> dict[str, float]:  # type: ignore[override]
        return self._parse_class_map(self.RIDE_CLASS_MULTIPLIERS_RAW)

    # Per-class minimum fare in cents (floor after multipliers & surge)
    RIDE_CLASS_MIN_FARE_CENTS_RAW: str = os.getenv(
        "RIDE_CLASS_MIN_FARE_CENTS",
        "standard=0,comfort=0,yellow=0,vip=2000,van=1500,electro=0",
    )

    @property
    def RIDE_CLASS_MIN_FARE_CENTS(self) -> dict[str, int]:  # type: ignore[override]
        mp = self._parse_class_map(self.RIDE_CLASS_MIN_FARE_CENTS_RAW)
        return {k: int(float(v)) for k, v in mp.items()}

    # Per-class minimum driver balance (Taxi wallet) required to accept rides of that class
    RIDE_CLASS_MIN_DRIVER_BALANCE_CENTS_RAW: str = os.getenv(
        "RIDE_CLASS_MIN_DRIVER_BALANCE_CENTS",
        "standard=0,comfort=0,yellow=0,vip=5000,van=3000,electro=0",
    )

    @property
    def RIDE_CLASS_MIN_DRIVER_BALANCE_CENTS(self) -> dict[str, int]:  # type: ignore[override]
        mp = self._parse_class_map(self.RIDE_CLASS_MIN_DRIVER_BALANCE_CENTS_RAW)
        return {k: int(float(v)) for k, v in mp.items()}
    # MQTT (optional)
    MQTT_BROKER_HOST: str | None = os.getenv("MQTT_BROKER_HOST")
    MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    MQTT_TOPIC_PREFIX: str = os.getenv("MQTT_TOPIC_PREFIX", "taxi")
    # Caches
    MAPS_ROUTE_CACHE_SECS: int = int(os.getenv("MAPS_ROUTE_CACHE_SECS", "60"))
    # Rate limiting
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")  # memory|redis
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_AUTH_BOOST: int = int(os.getenv("RATE_LIMIT_AUTH_BOOST", "2"))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RATE_LIMIT_REDIS_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_PREFIX", "rl_taxi")
    # OTP
    OTP_MODE: str = os.getenv("OTP_MODE", "dev")
    OTP_TTL_SECS: int = int(os.getenv("OTP_TTL_SECS", "300"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    OTP_DEV_CODE: str = os.getenv("OTP_DEV_CODE", "123456")
    OTP_SMS_PROVIDER: str = os.getenv("OTP_SMS_PROVIDER", "log")  # log|http
    OTP_SMS_SENDER_NAME: str = os.getenv("OTP_SMS_SENDER_NAME", "Taxi")
    OTP_SMS_TEMPLATE: str = os.getenv("OTP_SMS_TEMPLATE", "Your Taxi verification code is {code}")
    OTP_SMS_HTTP_URL: str = os.getenv("OTP_SMS_HTTP_URL", "")
    OTP_SMS_HTTP_AUTH_TOKEN: str = os.getenv("OTP_SMS_HTTP_AUTH_TOKEN", "")
    # Dev: optionally hide/disable OTP endpoints
    DEV_DISABLE_OTP: bool = env_bool("DEV_DISABLE_OTP", default=False)
    # Fraud / Risk controls
    FRAUD_RIDER_WINDOW_SECS: int = int(os.getenv("FRAUD_RIDER_WINDOW_SECS", "60"))
    FRAUD_RIDER_MAX_REQUESTS: int = int(os.getenv("FRAUD_RIDER_MAX_REQUESTS", "6"))
    FRAUD_DRIVER_LOC_MAX_AGE_SECS: int = int(os.getenv("FRAUD_DRIVER_LOC_MAX_AGE_SECS", "300"))
    FRAUD_MAX_ACCEPT_DIST_KM: float = float(os.getenv("FRAUD_MAX_ACCEPT_DIST_KM", "3.0"))
    FRAUD_MAX_START_DIST_KM: float = float(os.getenv("FRAUD_MAX_START_DIST_KM", "0.3"))
    FRAUD_MAX_COMPLETE_DIST_KM: float = float(os.getenv("FRAUD_MAX_COMPLETE_DIST_KM", "0.5"))
    FRAUD_CANCEL_WINDOW_RIDES: int = int(os.getenv("FRAUD_CANCEL_WINDOW_RIDES", "10"))
    FRAUD_CANCEL_MAX_RATIO: float = float(os.getenv("FRAUD_CANCEL_MAX_RATIO", "0.7"))
    FRAUD_MIN_TRIP_KM: float = float(os.getenv("FRAUD_MIN_TRIP_KM", "0.2"))
    FRAUD_AUTOSUSPEND_ON_VELOCITY: bool = os.getenv("FRAUD_AUTOSUSPEND_ON_VELOCITY", "false").lower() == "true"
    FRAUD_AUTOSUSPEND_MINUTES: int = int(os.getenv("FRAUD_AUTOSUSPEND_MINUTES", "10"))
    # Admin
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "")
    ADMIN_IP_ALLOWLIST: str = os.getenv("ADMIN_IP_ALLOWLIST", "")  # comma-separated IPs
    ADMIN_TOKEN_SHA256: str = os.getenv("ADMIN_TOKEN_SHA256", "")  # comma-separated lowercase hex digests
    # Matching & Reassign
    ASSIGNMENT_ACCEPT_TIMEOUT_SECS: int = int(os.getenv("ASSIGNMENT_ACCEPT_TIMEOUT_SECS", "120"))
    REASSIGN_SCAN_LIMIT: int = int(os.getenv("REASSIGN_SCAN_LIMIT", "200"))
    REASSIGN_RADIUS_FACTOR: float = float(os.getenv("REASSIGN_RADIUS_FACTOR", "1.0"))
    REASSIGN_RELAX_WALLET: bool = os.getenv("REASSIGN_RELAX_WALLET", "false").lower() == "true"
    ACCEPTED_START_TIMEOUT_SECS: int = int(os.getenv("ACCEPTED_START_TIMEOUT_SECS", "300"))
    # JWT & internal secrets rotation
    JWT_SECRET_PREV: str | None = os.getenv("JWT_SECRET_PREV")
    JWT_SECRETS_LIST_RAW: str | None = os.getenv("JWT_SECRETS")
    PAYMENTS_INTERNAL_SECRET_PREV: str | None = os.getenv("PAYMENTS_INTERNAL_SECRET_PREV")
    PAYMENTS_INTERNAL_SECRETS_RAW: str | None = os.getenv("PAYMENTS_INTERNAL_SECRETS")

    @property
    def jwt_expires_delta(self) -> timedelta:
        return timedelta(minutes=self.JWT_EXPIRES_MINUTES)

    @property
    def JWT_SECRETS(self) -> list[str]:  # current-first
        secrets: list[str] = []
        if self.JWT_SECRETS_LIST_RAW:
            secrets.extend([s.strip() for s in self.JWT_SECRETS_LIST_RAW.split(',') if s.strip()])
        if self.JWT_SECRET and self.JWT_SECRET not in secrets:
            secrets.insert(0, self.JWT_SECRET)
        if self.JWT_SECRET_PREV and self.JWT_SECRET_PREV not in secrets:
            secrets.append(self.JWT_SECRET_PREV)
        return secrets

    @property
    def PAYMENTS_INTERNAL_SECRETS(self) -> list[str]:  # current-first
        secrets: list[str] = []
        if self.PAYMENTS_INTERNAL_SECRETS_RAW:
            secrets.extend([s.strip() for s in self.PAYMENTS_INTERNAL_SECRETS_RAW.split(',') if s.strip()])
        if self.PAYMENTS_INTERNAL_SECRET and self.PAYMENTS_INTERNAL_SECRET not in secrets:
            secrets.insert(0, self.PAYMENTS_INTERNAL_SECRET)
        if self.PAYMENTS_INTERNAL_SECRET_PREV and self.PAYMENTS_INTERNAL_SECRET_PREV not in secrets:
            secrets.append(self.PAYMENTS_INTERNAL_SECRET_PREV)
        return secrets

    @property
    def admin_token_hashes(self) -> list[str]:
        raw = (self.ADMIN_TOKEN_SHA256 or "").split(',')
        return [r.strip().lower() for r in raw if r.strip()]


settings = Settings()

# Harden secrets for non-dev environments
if not settings.DEV_MODE:
    if not settings.ALLOWED_ORIGINS or "*" in settings.ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS must list explicit origins when ENV!=dev")
    if settings.AUTO_CREATE_SCHEMA:
        raise RuntimeError("AUTO_CREATE_SCHEMA cannot be enabled when ENV!=dev")
    if getattr(settings, "OTP_MODE", None) == "dev":
        raise RuntimeError("OTP_MODE=dev is not permitted when ENV!=dev")
    # Rate limiter must be redis in prod
    if settings.RATE_LIMIT_BACKEND.lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
    if not settings.REDIS_URL or not settings.REDIS_URL.startswith("redis://"):
        raise RuntimeError("REDIS_URL must be set to a redis:// URL when ENV!=dev")
    # JWT secrets or JWKS must be provided
    jwks = os.getenv("JWT_JWKS_URL", "").strip()
    if not jwks:
        jwt_secrets = settings.JWT_SECRETS
        if not jwt_secrets or any(s in ("", "change_me_in_prod") for s in jwt_secrets):
            raise RuntimeError("Provide secure JWT secrets (JWT_SECRET or JWT_SECRETS) when ENV!=dev (or set JWT_JWKS_URL)")
        if any(len(s) < 16 for s in jwt_secrets):
            raise RuntimeError("JWT secrets must be at least 16 characters long")
    # Internal API secrets (Payments)
    pin_secrets = settings.PAYMENTS_INTERNAL_SECRETS
    if not pin_secrets or any(s in ("", "dev_secret") for s in pin_secrets):
        raise RuntimeError("Provide secure PAYMENTS_INTERNAL_SECRET(S) when ENV!=dev")
    if any(len(s) < 32 for s in pin_secrets):
        raise RuntimeError("PAYMENTS internal secret(s) must be at least 32 characters long")
    if not settings.ADMIN_TOKEN and not settings.admin_token_hashes:
        raise RuntimeError("Provide ADMIN_TOKEN or ADMIN_TOKEN_SHA256 when ENV!=dev")
    if settings.OTP_SMS_PROVIDER.lower() == "http" and not settings.OTP_SMS_HTTP_URL:
        raise RuntimeError("OTP_SMS_HTTP_URL must be set when OTP_SMS_PROVIDER=http")
    if not settings.GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY must be set when ENV!=dev")
