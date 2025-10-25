from fastapi import FastAPI, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

# Import Food domain app primitives via PYTHONPATH=apps/food
from app.config import settings
from app.database import engine
from app.models import Base
from app.middleware_request_id import RequestIDMiddleware
from app.middleware_rate_limit import SlidingWindowLimiter
from app.middleware_rate_limit_redis import RedisRateLimiter
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
import json
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

from app.routers import auth as auth_router
from app.routers import courier as courier_router
from app.auth import get_current_user
from app.database import get_db
from app.models import User, Order


def create_app() -> FastAPI:
    app = FastAPI(title="Food Courier API", version="0.1.0")

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

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)

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

    # OpenAPI: add global HTTP Bearer scheme
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version="0.1.0",
            routes=app.routes,
        )
        tags_meta = [
            {"name": "auth", "description": "Phone OTP and JWT authentication"},
            {"name": "courier", "description": "Courier actions: accept, pickup, deliver orders"},
            {"name": "dashboard", "description": "Operator dashboard overview"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
            {"name": "about", "description": "Service information"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
        no_auth_paths = ["/health", "/health/deps", "/info", "/openapi.yaml"]
        for p in no_auth_paths:
            if p in openapi_schema.get("paths", {}):
                for op in openapi_schema["paths"][p].values():
                    op["security"] = []
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    app.include_router(auth_router.router)
    app.include_router(courier_router.router)

    @app.get("/me", tags=["dashboard"])
    def me(user: User = Depends(get_current_user), db = Depends(get_db)):
        assigned = db.query(Order).filter(Order.courier_user_id == user.id).count()
        delivering = db.query(Order).filter(Order.courier_user_id == user.id, Order.status == "out_for_delivery").count()
        from datetime import datetime, timedelta
        now = datetime.utcnow(); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        d7 = db.query(Order).filter(Order.courier_user_id == user.id, Order.status == "delivered", Order.created_at >= since7).count()
        d30 = db.query(Order).filter(Order.courier_user_id == user.id, Order.status == "delivered", Order.created_at >= since30).count()
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name},
            "orders_assigned": int(assigned),
            "orders_out_for_delivery": int(delivering),
            "metrics": {"7d": {"orders_delivered": int(d7)}, "30d": {"orders_delivered": int(d30)}},
        }
    @app.get("/health/deps", tags=["health"])
    def health_deps():
        out = {}
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("select 1")
            out["db"] = "ok"
        except Exception as e:
            out["db"] = f"error: {e.__class__.__name__}"
        try:
            import os
            ru = getattr(settings, "REDIS_URL", None) or os.getenv("REDIS_URL", "")
            if ru:
                from redis import Redis
                r = Redis.from_url(ru)
                r.ping()
                out["redis"] = "ok"
            else:
                out["redis"] = "skip"
        except Exception as e:
            out["redis"] = f"error: {e.__class__.__name__}"
        return out
    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Food Courier API", "version": "0.1.0", "env": settings.ENV}
    
    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml():
        spec = app.openapi()
        try:
            import yaml  # type: ignore
            return PlainTextResponse(yaml.safe_dump(spec, sort_keys=False), media_type="application/yaml")
        except Exception:
            return PlainTextResponse(json.dumps(spec, indent=2), media_type="application/yaml")

    @app.get("/ui", include_in_schema=False)
    def ui():
        html = f"""
<!doctype html>
<meta charset=\"utf-8\">
<title>{app.title} – Test UI</title>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px}}
  button,input,select{{font-size:14px;margin:4px;padding:6px 8px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  .card{{border:1px solid #e5e7eb;border-radius:8px;padding:12px}}
  pre{{background:#f7f7f7;padding:10px;border-radius:6px}}
</style>
<h1>{app.title}</h1>
<div class=\"grid\">
  <div class=\"card\">
    <h3>Base</h3>
    <div>
      <label>Bearer Token:</label>
      <input id=\"tok\" size=\"60\" placeholder=\"paste JWT…\">
      <button onclick=\"me()\">/me</button>
      <button onclick=\"info()\">/info</button>
      <button onclick=\"health()\">/health</button>
      <a href=\"/docs\" target=\"_blank\">/docs</a>
      <a href=\"/openapi.yaml\" target=\"_blank\">/openapi.yaml</a>
    </div>
    <pre id=\"out\"></pre>
  </div>
  <div class=\"card\">
    <h3>Courier</h3>
    <div>
      <button onclick=\"listAvail()\">Available Orders</button>
      <input id=\"oid\" size=\"36\" placeholder=\"order_id\">
      <button onclick=\"accept()\">Accept</button>
    </div>
    <div>
      <button onclick=\"myOrders()\">My Orders</button>
      <button onclick=\"picked()\">Picked Up</button>
      <button onclick=\"delivered()\">Delivered</button>
    </div>
    <div>
      <input id=\"lat\" placeholder=\"lat\" style=\"width:120px\">
      <input id=\"lon\" placeholder=\"lon\" style=\"width:120px\">
      <button onclick=\"ping()\">Update Location</button>
    </div>
    <pre id=\"cout\"></pre>
  </div>
</div>
<script>
const out=document.getElementById('out');
const cout=document.getElementById('cout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function listAvail(){ const r=await fetch('/courier/available',{headers:auth()}); cout.textContent=await r.text(); }
async function accept(){ const id=document.getElementById('oid').value.trim(); const r=await fetch('/courier/orders/'+id+'/accept',{method:'POST', headers:auth()}); cout.textContent=await r.text(); }
async function myOrders(){ const r=await fetch('/courier/orders',{headers:auth()}); cout.textContent=await r.text(); }
async function picked(){ const id=document.getElementById('oid').value.trim(); const r=await fetch('/courier/orders/'+id+'/picked_up',{method:'POST', headers:auth()}); cout.textContent=await r.text(); }
async function delivered(){ const id=document.getElementById('oid').value.trim(); const r=await fetch('/courier/orders/'+id+'/delivered',{method:'POST', headers:auth()}); cout.textContent=await r.text(); }
async function ping(){ const id=document.getElementById('oid').value.trim(); const body={lat: parseFloat(lat.value), lon: parseFloat(lon.value)}; const r=await fetch('/courier/orders/'+id+'/location',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); cout.textContent=await r.text(); }
</script>
"""
        return PlainTextResponse(html, media_type="text/html; charset=utf-8")
    
    @app.get("/", include_in_schema=False)
    def root():
        return {
            "service": app.title,
            "links": {
                "docs": "/docs",
                "openapi": "/openapi.yaml",
                "health": "/health",
                "info": "/info",
                "metrics": "/metrics",
            },
        }
    return app


app = create_app()
