from fastapi import FastAPI, Response, Request, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

# Import Payments domain via PYTHONPATH=apps/payments
from app.config import settings
from app.database import engine
from app.models import Base
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
import json
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

from app.routers import merchant_api as merchant_api_router
from app.database import get_db
from app.utils.merchant_api import verify_request


def create_app() -> FastAPI:
    app = FastAPI(title="Payments Merchant API", version="0.1.0")

    # Optional Sentry init
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn and sentry_sdk is not None:
        try:
            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")))
        except Exception:
            pass

    allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if getattr(settings, "AUTO_CREATE_SCHEMA", False):
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

    @app.get("/health", tags=["health"])
    def health():
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return {"status": "ok", "env": settings.ENV}

    REQ = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])

    @app.middleware("http")
    async def _metrics_mw(request, call_next):
        response = await call_next(request)
        try:
            REQ.labels(request.method, request.url.path, str(response.status_code)).inc()
        except Exception:
            pass
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Payments Merchant API", "version": "0.1.0", "env": settings.ENV}

    app.include_router(merchant_api_router.router)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # OpenAPI: add global HTTP Bearer scheme (merchant HMAC; still display bearer for admin/protected endpoints if any)
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version="0.1.0",
            routes=app.routes,
        )
        tags_meta = [
            {"name": "merchant-api", "description": "HMAC-authenticated merchant API"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
            {"name": "about", "description": "Service information"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
        no_auth_paths = ["/health", "/openapi.yaml", "/info"]
        for p in no_auth_paths:
            if p in openapi_schema.get("paths", {}):
                for op in openapi_schema["paths"][p].values():
                    op["security"] = []
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    @app.get("/merchant/api/ping", tags=["merchant-api"])
    def merchant_ping(
        request: Request,
        db = get_db,
        key_id: str | None = Header(default=None, alias="X-API-Key"),
        sign: str | None = Header(default=None, alias="X-API-Sign"),
        ts: str | None = Header(default=None, alias="X-API-Ts"),
    ):
        if not key_id or not sign or not ts:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing headers")
        _db = next(db())
        try:
            user_id = verify_request(_db, key_id, sign, ts, str(request.url.path), b"")
            if user_id is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
            return {"detail": "ok", "user_id": str(user_id)}
        finally:
            _db.close()
    
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
                "merchant_ping": "/merchant/api/ping",
            },
        }

    @app.get("/ui", include_in_schema=False)
    def ui():
        html = f"""
<!doctype html>
<meta charset=\"utf-8\">
<title>{app.title} – Test UI</title>
<style>body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px}}button,input{{font-size:14px;margin:4px;padding:6px 8px}}</style>
<h1>{app.title}</h1>
<div>
  <button onclick=\"info()\">/info</button>
  <button onclick=\"health()\">/health</button>
  <a href=\"/docs\" target=\"_blank\">/docs</a>
  <a href=\"/openapi.yaml\" target=\"_blank\">/openapi.yaml</a>
  <pre id=\"out\"></pre>
</div>
<script>
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
const out=document.getElementById('out');
</script>
"""
        return PlainTextResponse(html, media_type="text/html; charset=utf-8")
    return app


app = create_app()
