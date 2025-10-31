from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
from .routers import trips as trips_router
from .routers import bookings as bookings_router
from .routers import promos as promos_router
from .routers import operators as operators_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .middleware_request_id import RequestIDMiddleware
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter
from .utils.security import SecurityHeadersMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
import json
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None


def create_app() -> FastAPI:
    # Optional Sentry init (no-op if DSN missing)
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn and sentry_sdk is not None:
        try:
            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")))
        except Exception:
            pass
    app = FastAPI(title="Bus API", version="0.1.0")

    # CORS: avoid browsers blocking preflights if using wildcard origins
    allowed_origins = settings.ALLOWED_ORIGINS or []
    allow_credentials = True
    if not allowed_origins:
        # Public API without browser credentials when no explicit origins are set
        allowed_origins = ["*"]
        allow_credentials = False
    if "*" in allowed_origins:
        allow_credentials = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # Request ID + JSON logs + security + gzip
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)
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
        # best-effort lightweight alterations for dev: add new columns if missing
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("ALTER TABLE IF EXISTS bus_promo_codes ADD COLUMN IF NOT EXISTS operator_id UUID NULL")
                conn.exec_driver_sql("ALTER TABLE IF EXISTS trips ADD COLUMN IF NOT EXISTS vehicle_id UUID NULL")
                conn.exec_driver_sql("ALTER TABLE IF EXISTS operator_members ADD COLUMN IF NOT EXISTS branch_id UUID NULL")
                conn.exec_driver_sql("ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS operator_branch_id UUID NULL")
                # create branches table if not exists (idempotent via create_all)
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS bus_operator_webhooks (id UUID PRIMARY KEY, operator_id UUID NOT NULL, url VARCHAR(512) NOT NULL, secret VARCHAR(256) NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL)")
        except Exception:
            pass

    @app.get("/health")
    def health():
        from .database import engine
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
    app.include_router(trips_router.router)
    app.include_router(bookings_router.router)
    app.include_router(promos_router.router)
    app.include_router(operators_router.router)
    
    # OpenAPI customization: provide YAML and mark public routes unauthenticated
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(title=app.title, version="0.1.0", routes=app.routes)
        tags_meta = [
            {"name": "auth", "description": "Phone OTP and JWT authentication"},
            {"name": "trips", "description": "Search and list bus trips"},
            {"name": "bookings", "description": "Reserve, confirm, cancel bookings and tickets"},
            {"name": "promos", "description": "Promo codes lookup"},
            {"name": "operators", "description": "Operator admin endpoints"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
        no_auth_paths = {"/health", "/metrics", "/openapi.yaml", "/openapi.json"}
        for p, ops in openapi_schema.get("paths", {}).items():
            if p in no_auth_paths:
                for op in ops.values():
                    op["security"] = []
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml():
        spec = app.openapi()
        try:
            import yaml  # type: ignore
            return PlainTextResponse(yaml.safe_dump(spec, sort_keys=False), media_type="application/yaml")
        except Exception:
            return PlainTextResponse(json.dumps(spec, indent=2), media_type="application/yaml")

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "service": app.title,
            "links": {
                "docs": "/docs",
                "openapi": "/openapi.yaml",
                "health": "/health",
                "metrics": "/metrics",
            },
        }
    return app


app = create_app()
