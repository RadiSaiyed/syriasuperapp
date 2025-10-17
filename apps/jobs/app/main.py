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
from .routers import employer as employer_router
from .routers import jobs as jobs_router
from .routers import applications as applications_router
from .routers import webhooks as webhooks_router
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import threading, time
import httpx


def create_app() -> FastAPI:
    app = FastAPI(title="Jobs API", version="0.1.0")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    if settings.RATE_LIMIT_BACKEND == "redis":
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
    app.include_router(employer_router.router)
    app.include_router(jobs_router.router)
    app.include_router(applications_router.router)
    app.include_router(webhooks_router.router)
    
    # Background cron: dispatch scheduled taxi rides (dev-only endpoint)
    def _cron_loop():
        url = f"{settings.TAXI_BASE_URL}/rides/dispatch_scheduled"
        interval = max(10, int(settings.TAXI_DISPATCH_INTERVAL_SECS))
        while True:
            try:
                with httpx.Client(timeout=5.0) as client:
                    client.post(url)
            except Exception:
                pass
            time.sleep(interval)

    try:
        threading.Thread(target=_cron_loop, daemon=True).start()
    except Exception:
        pass
    return app


app = create_app()
