from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .config import settings
from .routers import ai as ai_router
from .routers import rag as rag_router
from .routers import ocr as ocr_router
from .routers import tools as tools_router
from .routers import risk as risk_router
from .routers import digest as digest_router
from .routers import membership as membership_router
from .routers import missions as missions_router
from .routers import pricing as pricing_router
from .routers import cv as cv_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Gateway", version="0.1.0")

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "env": settings.ENV}

    REQ = Counter("http_requests_total", "HTTP requests", ["method", "path", "status", "service"])
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
            REQ.labels(request.method, route, str(response.status_code), "ai_gateway").inc()
            REQ_DURATION.labels(request.method, route).observe(duration)
        except Exception:
            pass
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(ai_router.router)
    app.include_router(rag_router.router)
    app.include_router(ocr_router.router)
    app.include_router(tools_router.router)
    app.include_router(risk_router.router)
    app.include_router(digest_router.router)
    app.include_router(membership_router.router)
    app.include_router(missions_router.router)
    app.include_router(pricing_router.router)
    app.include_router(cv_router.router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.APP_HOST, port=settings.APP_PORT)
