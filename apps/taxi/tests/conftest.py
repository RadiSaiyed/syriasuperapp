import os
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[3]
_LIBS_DIR = _ROOT / "libs"
_SHARED_PATH = _LIBS_DIR / "superapp_shared"
if _SHARED_PATH.exists():
    sys.path.insert(0, str(_SHARED_PATH))


os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")

# Relax fraud controls so functional tests can run multiple ride requests quickly
os.environ.setdefault("FRAUD_RIDER_MAX_REQUESTS", "100000")
os.environ.setdefault("FRAUD_RIDER_WINDOW_SECS", "1")
os.environ.setdefault("FRAUD_AUTOSUSPEND_ON_VELOCITY", "false")
os.environ.setdefault("FRAUD_MAX_ACCEPT_DIST_KM", "1000")
os.environ.setdefault("FRAUD_MAX_START_DIST_KM", "1000")
os.environ.setdefault("FRAUD_MAX_COMPLETE_DIST_KM", "1000")

# Keep global rate limit generous; specific tests can override as needed
os.environ.setdefault("RL_LIMIT_PER_MINUTE_OVERRIDE", "1000")
os.environ.setdefault("RL_AUTH_BOOST_OVERRIDE", "10")


def _relax_in_memory_rate_limiter() -> None:
    """Monkeypatch the in-memory rate limiter to skip throttling during tests."""
    try:
        from superapp_shared import rate_limit as _rl
    except Exception:
        return
    orig_dispatch = _rl.SlidingWindowLimiter.dispatch

    async def _patched_dispatch(self, request, call_next):  # type: ignore
        if os.getenv("RL_TEST_DISABLE", "true").lower() == "true":
            return await call_next(request)
        return await orig_dispatch(self, request, call_next)

    _rl.SlidingWindowLimiter.dispatch = _patched_dispatch  # type: ignore


_relax_in_memory_rate_limiter()
