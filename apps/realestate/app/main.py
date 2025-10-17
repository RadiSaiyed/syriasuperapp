from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .config import settings
from .database import engine
from .models import Base, User
from .schemas import TokenOut, RequestOtpIn, VerifyOtpIn
from .auth import ensure_user, _make_token, _verify_dev_otp
from .routers import listings as listings_router
from .routers import favorites as favorites_router
from .routers import inquiries as inquiries_router
from .routers import admin as admin_router
from .routers import reservations as reservations_router
from .routers import owner as owner_router


def create_app() -> FastAPI:
    app = FastAPI(title="Real Estate API", version="0.1.0", docs_url="/docs")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    @app.post("/auth/request_otp")
    def request_otp(payload: RequestOtpIn):
        # DEV: accept any phone, OTP fixed
        return {"detail": "otp_sent"}

    @app.post("/auth/verify_otp", response_model=TokenOut)
    def verify_otp(payload: VerifyOtpIn):
        if not _verify_dev_otp(payload.phone, payload.otp):
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_otp")
        from .database import get_db
        db = next(get_db())
        try:
            u = ensure_user(db, payload.phone, payload.name)
            token = _make_token(str(u.id))
        finally:
            db.close()
        return TokenOut(access_token=token)

    app.include_router(listings_router.router)
    app.include_router(favorites_router.router)
    app.include_router(inquiries_router.router)
    app.include_router(admin_router.router)
    app.include_router(reservations_router.router)
    app.include_router(owner_router.router)
    return app


app = create_app()
