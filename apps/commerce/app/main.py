from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
try:
    from starlette.middleware.forwarded import ForwardedMiddleware as _ForwardedOrProxy
except Exception:
    try:
        from starlette.middleware.proxy_headers import ProxyHeadersMiddleware as _ForwardedOrProxy
    except Exception:
        _ForwardedOrProxy = None  # type: ignore
from sqlalchemy import text

from .config import settings
from .database import engine
from .models import Base
from .routers import auth as auth_router
from .routers import shops as shops_router
from .routers import cart as cart_router
from .routers import orders as orders_router
from .routers import promos as promos_router
from .routers import wishlist as wishlist_router
from .routers import reviews as reviews_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .middleware_request_id import RequestIDMiddleware
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter


_DB_OK = True


def create_app() -> FastAPI:
    app = FastAPI(title="Commerce API", version="0.1.0")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestIDMiddleware)
    # Trusted hosts + forwarded headers
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or (["*"] if settings.ENV != "prod" else ["api.example.com"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    proxy_trusted = getattr(settings, "PROXY_TRUSTED_IPS", None)
    if proxy_trusted and _ForwardedOrProxy:
        try:
            app.add_middleware(_ForwardedOrProxy, trusted_hosts=proxy_trusted)
        except Exception:
            pass

    # Rate limit
    backend = (getattr(settings, "RATE_LIMIT_BACKEND", "") or "").lower()
    common_excludes = ["/health", "/health/deps", "/metrics", "/info", "/openapi.yaml", "/openapi.json", "/ui", "/docs"]
    if backend == "redis":
        app.add_middleware(
            RedisRateLimiter,
            redis_url=settings.REDIS_URL,
            limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            auth_boost=settings.RATE_LIMIT_AUTH_BOOST,
            prefix=settings.RATE_LIMIT_REDIS_PREFIX,
            exclude_paths=common_excludes,
        )
    else:
        app.add_middleware(
            SlidingWindowLimiter,
            limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            auth_boost=settings.RATE_LIMIT_AUTH_BOOST,
            exclude_paths=common_excludes,
        )

    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)

    @app.get("/health")
    def health():
        # Constant-time health: return cached DB status to avoid edge timeouts.
        ok = True
        try:
            ok = bool(globals().get("_DB_OK", True))
        except Exception:
            ok = True
        return {"status": "ok", "env": settings.ENV, "db": ("ok" if ok else "degraded")}

    # Background DB probe (best-effort)
    @app.on_event("startup")
    async def _start_db_probe():
        import threading, time

        def _probe():
            while True:
                try:
                    with engine.connect() as conn:
                        conn.exec_driver_sql("SELECT 1")
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
    app.include_router(shops_router.router)
    app.include_router(cart_router.router)
    app.include_router(orders_router.router)
    app.include_router(promos_router.router)
    app.include_router(wishlist_router.router)
    app.include_router(reviews_router.router)
    return app


app = create_app()
