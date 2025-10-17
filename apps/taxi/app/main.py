from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import engine
from .models import Base
from .routers import auth as auth_router
from .routers import driver as driver_router
from .routers import rides as rides_router
from .routers import partners as partners_router
from .routers import ws as ws_router
from .routers import favorites as favorites_router
from .routers import promos as promos_router
from .routers import maps_api as maps_router
from .routers import scheduled as scheduled_router
from .routers import taxi_wallet as taxi_wallet_router
from .routers import admin as admin_router
from .routers import push as push_router
from .routers import wallet as wallet_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from .middleware_request_id import RequestIDMiddleware
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None


def create_app() -> FastAPI:
    # Optional Sentry init
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn and sentry_sdk is not None:
        try:
            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")))
        except Exception:
            pass
    app = FastAPI(title="Taxi API", version="0.1.0")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID + JSON logs
    app.add_middleware(RequestIDMiddleware)

    # Rate limit
    if settings.RATE_LIMIT_BACKEND.lower() == "redis":
        app.add_middleware(
            RedisRateLimiter,
            redis_url=settings.REDIS_URL,
            limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            auth_boost=settings.RATE_LIMIT_AUTH_BOOST,
            prefix=settings.RATE_LIMIT_REDIS_PREFIX,
        )
    else:
        app.add_middleware(
            SlidingWindowLimiter,
            limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            auth_boost=settings.RATE_LIMIT_AUTH_BOOST,
        )

    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
        # Ensure new/optional columns exist (dev convenience only)
        try:
            with engine.connect() as conn:
                # Postgres syntax: ALTER TABLE IF EXISTS ... ADD COLUMN IF NOT EXISTS ...
                conn.execute(text("ALTER TABLE IF EXISTS rides ADD COLUMN IF NOT EXISTS ride_class TEXT"))
                conn.execute(text("ALTER TABLE IF EXISTS drivers ADD COLUMN IF NOT EXISTS ride_class TEXT"))
                # Additional ride fields used by newer code paths
                conn.execute(text("ALTER TABLE IF EXISTS rides ADD COLUMN IF NOT EXISTS passenger_name TEXT"))
                conn.execute(text("ALTER TABLE IF EXISTS rides ADD COLUMN IF NOT EXISTS passenger_phone TEXT"))
                conn.execute(text("ALTER TABLE IF EXISTS rides ADD COLUMN IF NOT EXISTS payer_mode TEXT"))
                conn.commit()
        except Exception:
            pass
    # Ensure PostGIS extension exists (no-op if already created)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()
    except Exception:
        pass

    @app.get("/health")
    def health():
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return {"status": "ok", "env": settings.ENV}

    REQ = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
    REQ_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )

    @app.middleware("http")
    async def _metrics_mw(request, call_next):
        import time
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        try:
            route = getattr(request.scope.get("route"), "path", None) or request.url.path
            REQ.labels(request.method, route, str(response.status_code)).inc()
            REQ_DURATION.labels(request.method, route).observe(duration)
        except Exception:
            pass
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(auth_router.router)
    app.include_router(driver_router.router)
    app.include_router(rides_router.router)
    app.include_router(partners_router.router)
    app.include_router(ws_router.router)
    app.include_router(favorites_router.router)
    app.include_router(promos_router.router)
    app.include_router(maps_router.router)
    app.include_router(scheduled_router.router)
    app.include_router(taxi_wallet_router.router)
    app.include_router(wallet_router.router)
    app.include_router(push_router.router)
    admin_enabled = bool(getattr(settings, "ADMIN_TOKEN", "") or os.getenv("ADMIN_TOKEN_SHA256", "") or getattr(settings, "admin_token_hashes", []))
    if admin_enabled:
        app.include_router(admin_router.router)
    return app


app = create_app()
