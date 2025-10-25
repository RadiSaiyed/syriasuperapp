import os


class Settings:
    ENV: str = os.getenv("ENV", "dev")
    DEV_MODE: bool = ENV.lower() == "dev"
    # Optional basic auth for the UI/API
    OPS_ADMIN_BASIC_USER: str = os.getenv("OPS_ADMIN_BASIC_USER", "")
    OPS_ADMIN_BASIC_PASS: str = os.getenv("OPS_ADMIN_BASIC_PASS", "")
    # Rate limiting config (not used directly by app yet, but enforced for prod parity)
    RATE_LIMIT_BACKEND: str = os.getenv("RATE_LIMIT_BACKEND", "memory")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")


settings = Settings()

# Harden for non‑dev environments
if not settings.DEV_MODE:
    # Require basic auth credentials to be configured
    if not settings.OPS_ADMIN_BASIC_USER or not settings.OPS_ADMIN_BASIC_PASS:
        raise RuntimeError("OPS_ADMIN_BASIC_USER and OPS_ADMIN_BASIC_PASS must be set when ENV!=dev")
    # Enforce redis rate limiter parity in prod
    if settings.RATE_LIMIT_BACKEND.lower() != "redis":
        raise RuntimeError("RATE_LIMIT_BACKEND must be 'redis' when ENV!=dev")
    if not settings.REDIS_URL or not settings.REDIS_URL.startswith("redis://"):
        raise RuntimeError("REDIS_URL must be set to a redis:// URL when ENV!=dev")

