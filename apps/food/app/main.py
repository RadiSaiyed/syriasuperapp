from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import engine
from .models import Base
from .middleware_request_id import RequestIDMiddleware
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter
from .routers import auth as auth_router
from .routers import restaurants as restaurants_router
from .routers import cart as cart_router
from .routers import orders as orders_router
from .routers import admin as admin_router
from .routers import courier as courier_router
from .routers import webhooks as webhooks_router
from .routers import payments_webhook as payments_webhook_router
from .routers import reviews as reviews_router
from .routers import favorites as favorites_router
from .routers import operator as operator_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .utils.webhooks import process_pending_once
import threading, time


_DB_OK = True


def create_app() -> FastAPI:
    app = FastAPI(title="Food Delivery API", version="0.1.0")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

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
        # Lightweight evolution for newly added columns in dev/demo
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS hours_json TEXT")
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS is_open_override BOOLEAN")
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS special_hours_json TEXT")
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS busy_mode BOOLEAN DEFAULT FALSE")
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS max_orders_per_hour INTEGER")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS preparing_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS out_for_delivery_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS last_status_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS kds_bumped BOOLEAN DEFAULT FALSE")
                conn.exec_driver_sql("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS packed BOOLEAN DEFAULT FALSE")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS visible BOOLEAN DEFAULT TRUE")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS category_id UUID")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS stock_qty INTEGER")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS oos_until TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS station VARCHAR(32)")
                conn.exec_driver_sql("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS station_snapshot VARCHAR(32)")
                # Create new tables if not exist (best-effort)
                conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS menu_categories (
                    id UUID PRIMARY KEY,
                    restaurant_id UUID NOT NULL REFERENCES restaurants(id),
                    parent_id UUID NULL REFERENCES menu_categories(id),
                    name VARCHAR(128) NOT NULL,
                    description VARCHAR(512) NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL
                )
                """)
                conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS modifier_groups (
                    id UUID PRIMARY KEY,
                    restaurant_id UUID NOT NULL REFERENCES restaurants(id),
                    name VARCHAR(128) NOT NULL,
                    min_choices INTEGER NOT NULL DEFAULT 0,
                    max_choices INTEGER NOT NULL DEFAULT 1,
                    required BOOLEAN NOT NULL DEFAULT FALSE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL
                )
                """)
                conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS modifier_options (
                    id UUID PRIMARY KEY,
                    group_id UUID NOT NULL REFERENCES modifier_groups(id),
                    name VARCHAR(128) NOT NULL,
                    price_delta_cents INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL
                )
                """)
                conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS menu_item_modifier_groups (
                    id UUID PRIMARY KEY,
                    menu_item_id UUID NOT NULL REFERENCES menu_items(id),
                    group_id UUID NOT NULL REFERENCES modifier_groups(id),
                    created_at TIMESTAMP NOT NULL,
                    CONSTRAINT uq_menu_item_group UNIQUE (menu_item_id, group_id)
                )
                """)
                conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id UUID PRIMARY KEY,
                    user_id UUID NULL REFERENCES users(id),
                    action VARCHAR(64) NOT NULL,
                    entity_type VARCHAR(64) NOT NULL,
                    entity_id VARCHAR(64) NULL,
                    before_json VARCHAR(4096) NULL,
                    after_json VARCHAR(4096) NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """)
                conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    id UUID PRIMARY KEY,
                    endpoint_id UUID NULL REFERENCES food_webhook_endpoints(id),
                    event VARCHAR(128) NOT NULL,
                    payload_json VARCHAR(4096) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error VARCHAR(512) NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """)
        except Exception:
            pass

    @app.get("/health")
    def health():
        ok = True
        try:
            ok = bool(globals().get("_DB_OK", True))
        except Exception:
            ok = True
        return {"status": "ok", "env": settings.ENV, "db": ("ok" if ok else "degraded")}

    @app.on_event("startup")
    async def _start_db_probe():
        import threading, time

        def _probe():
            while True:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("select 1"))
                    globals()["_DB_OK"] = True
                except Exception:
                    globals()["_DB_OK"] = False
                time.sleep(5)

        try:
            threading.Thread(target=_probe, daemon=True).start()
        except Exception:
            pass

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
    app.include_router(restaurants_router.router)
    app.include_router(cart_router.router)
    app.include_router(orders_router.router)
    app.include_router(admin_router.router)
    app.include_router(courier_router.router)
    app.include_router(webhooks_router.router)
    app.include_router(payments_webhook_router.router)
    app.include_router(reviews_router.router)
    app.include_router(favorites_router.router)
    app.include_router(operator_router.router)

    # Background webhook worker (dev/demo best-effort)
    if str(getattr(settings, "WEBHOOK_ENABLED", "false")).lower() in ("1","true","yes"):
        interval = int(getattr(settings, "WEBHOOK_WORKER_INTERVAL_SECS", 10))
        def _worker():
            while True:
                try:
                    process_pending_once()
                except Exception:
                    pass
                time.sleep(max(1, interval))
        try:
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
        except Exception:
            pass
    return app


app = create_app()
