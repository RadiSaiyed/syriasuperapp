import os


# Ensure sensible defaults for tests before app import
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("RL_EXEMPT_OTP", "true")


def _boost_limits():
    try:
        from app import config as cfg
        cfg.settings.RATE_LIMIT_BACKEND = "memory"
        cfg.settings.RATE_LIMIT_PER_MINUTE = 100000
        cfg.settings.RATE_LIMIT_AUTH_BOOST = 1
        # Keep OTP in dev mode unless a test opts into redis explicitly
        cfg.settings.OTP_MODE = "dev"
        cfg.settings.STARTING_CREDIT_CENTS = 0
    except Exception:
        # If config not importable yet, it's fine; tests that create custom apps will set themselves.
        pass


_boost_limits()
