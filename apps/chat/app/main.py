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
from .middleware_request_id import RequestIDMiddleware
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter
from .routers import auth as auth_router
from .routers import keys as keys_router
from .routers import contacts as contacts_router
from .routers import messages as messages_router
from .routers import groups as groups_router
from .routers import admin as admin_router
from .routers import presence as presence_router
from .routers import internal_tools as internal_tools_router
from .routers import payments_webhook as payments_webhook_router
from .routers import blocks as blocks_router
from .ws import router as ws_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


def create_app() -> FastAPI:
    app = FastAPI(title="Chat API", version="0.1.0")

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
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
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
    app.include_router(keys_router.router)
    app.include_router(contacts_router.router)
    app.include_router(messages_router.router)
    app.include_router(groups_router.router)
    app.include_router(admin_router.router)
    app.include_router(presence_router.router)
    app.include_router(blocks_router.router)
    app.include_router(ws_router)
    app.include_router(internal_tools_router.router)
    app.include_router(payments_webhook_router.router)
    # Dev-only helpers
    if settings.ENV.lower() == "dev":
        try:
            from .routers import dev_seed as dev_seed_router
            app.include_router(dev_seed_router.router)
        except Exception:
            pass
    return app


app = create_app()
