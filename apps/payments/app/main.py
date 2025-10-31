import os
import asyncio
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
from .database import engine, SessionLocal
from .models import Base
from .routers import auth as auth_router
from .routers import wallet as wallet_router
from .routers import payments as payments_router
from .routers import refunds as refunds_router
from .routers import links as links_router
from .routers import subscriptions as subscriptions_router
from .routers import requests as requests_router
from .routers import invoices as invoices_router
from .routers import passkeys as passkeys_router
from .routers import kyc as kyc_router
from .routers import cash as cash_router
from .routers import internal as internal_router
from .routers import merchant_api as merchant_api_router
from .routers import idp as idp_router
from .routers import webhooks as webhooks_router
from .routers import vouchers as vouchers_router
from .routers import admin as admin_router
from .errors import app_error_handler, http_exception_handler, AppError
from fastapi import HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .middleware_rate_limit import SlidingWindowLimiter
from .middleware_rate_limit_redis import RedisRateLimiter
from .middleware_request_id import RequestIDMiddleware
from .utils.security_headers import SecurityHeadersMiddleware

# Optional OpenTelemetry tracing (enabled via env OTEL_EXPORTER_OTLP_ENDPOINT)
def _init_tracing(app: FastAPI) -> None:
    try:
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or "http://localhost:4318"
        service_name = os.getenv("OTEL_SERVICE_NAME", "payments")
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            "service.name": service_name,
            "deployment.environment": settings.ENV,
        })
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
    except Exception:
        # Tracing is optional; fail-open
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="Payments API", version="0.1.0", docs_url="/docs")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID + JSON request log
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
    # Secure default HTTP headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting
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

    # Metrics
    REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
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
            # Prefer templated route if available to limit cardinality
            route = getattr(request.scope.get("route"), "path", None) or request.url.path
            REQUESTS.labels(request.method, route, str(response.status_code)).inc()
            # Attach exemplar with trace_id if available
            exemplar = None
            try:
                from opentelemetry import trace as _trace  # type: ignore
                ctx = _trace.get_current_span().get_span_context()
                if getattr(ctx, "trace_id", 0):
                    exemplar = {"trace_id": f"{ctx.trace_id:032x}"}
            except Exception:
                exemplar = None
            if exemplar:
                try:
                    REQ_DURATION.labels(request.method, route).observe(duration, exemplar=exemplar)  # type: ignore[call-arg]
                except Exception:
                    REQ_DURATION.labels(request.method, route).observe(duration)
            else:
                REQ_DURATION.labels(request.method, route).observe(duration)
        except Exception:
            pass
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Initialize tracing late to ensure app exists
    _init_tracing(app)

    app.include_router(auth_router.router)
    app.include_router(wallet_router.router)
    app.include_router(payments_router.router)
    app.include_router(refunds_router.router)
    app.include_router(links_router.router)
    app.include_router(subscriptions_router.router)
    app.include_router(requests_router.router)
    app.include_router(invoices_router.router)
    app.include_router(kyc_router.router)
    # Passkeys (dev scaffolding)
    if getattr(settings, "PASSKEYS_ENABLED", False):
        app.include_router(passkeys_router.router)
    app.include_router(cash_router.router)
    if settings.INTERNAL_API_SECRET:
        app.include_router(internal_router.router)
    app.include_router(merchant_api_router.router)
    app.include_router(webhooks_router.router)
    app.include_router(vouchers_router.router)
    admin_enabled = bool(os.getenv("ADMIN_TOKEN", "") or os.getenv("ADMIN_TOKEN_SHA256", "") or getattr(settings, "admin_token_hashes", []))
    if admin_enabled:
        app.include_router(admin_router.router)
    # JWKS (if RS256 enabled)
    app.include_router(idp_router.router)

    # Error handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Optional background scheduler for invoice autopay sweep
    try:
        poll = int(os.getenv("INVOICES_AUTOPAY_POLL_SECS", "0"))
    except Exception:
        poll = 0
    if poll > 0:
        @app.on_event("startup")
        async def _start_invoice_autopay_scheduler():
            async def _loop():
                while True:
                    try:
                        invoices_router.process_all_due_once()
                    except Exception:
                        pass
                    await asyncio.sleep(poll)
            asyncio.create_task(_loop())

    # Background worker for webhook deliveries (dev opt-in)
    try:
        wh_poll = int(os.getenv("WEBHOOK_WORKER_POLL_SECS", "0"))
    except Exception:
        wh_poll = 0
    if wh_poll > 0:
        @app.on_event("startup")
        async def _start_webhook_worker():
            async def _loop():
                while True:
                    try:
                        db = SessionLocal()
                        try:
                            webhooks_router._process_once(db, limit=50)  # type: ignore[attr-defined]
                        finally:
                            db.close()
                    except Exception:
                        pass
                    await asyncio.sleep(wh_poll)
            asyncio.create_task(_loop())

    return app


app = create_app()
