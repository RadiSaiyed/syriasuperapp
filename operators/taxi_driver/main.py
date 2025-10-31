from fastapi import FastAPI, Response, Depends
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

# Import Taxi domain app primitives via PYTHONPATH=apps/taxi
from app.config import settings
from app.database import engine
from app.models import Base
from app.middleware_request_id import RequestIDMiddleware
from app.middleware_rate_limit import SlidingWindowLimiter
from app.middleware_rate_limit_redis import RedisRateLimiter
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
from operators._shared.common import SecurityHeadersMiddleware, init_tracing
import json
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

from app.routers import auth as auth_router
from app.routers import driver as driver_router
from app.routers import taxi_wallet as taxi_wallet_router
from app.routers import push as push_router
from app.routers import ws as ws_router
from app.auth import get_current_user, get_db
from fastapi import HTTPException, status
from app.models import User, Driver, DriverLocation, Ride


def create_app() -> FastAPI:
    app = FastAPI(title="Taxi Driver API", version="0.1.0")

    # Optional Sentry init
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn and sentry_sdk is not None:
        try:
            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")))
        except Exception:
            pass

    # CORS: avoid '*' with credentials which browsers reject
    allowed_origins = settings.ALLOWED_ORIGINS or []
    allow_credentials = bool(getattr(settings, "CORS_ALLOW_CREDENTIALS", True))
    if not allowed_origins:
        # Public API without browser credentials when no explicit origins set
        allowed_origins = ["*"]
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # Request ID + Security headers + Compression
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # Rate limit
    common_excludes = ["/health", "/health/deps", "/metrics", "/info", "/openapi.yaml", "/openapi.json", "/ui", "/docs"]
    backend = (getattr(settings, "RATE_LIMIT_BACKEND", "") or "").lower()
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

    if getattr(settings, "AUTO_CREATE_SCHEMA", False):
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

    @app.get("/health", tags=["health"])
    def health():
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"status": "ok", "env": settings.ENV}

    REQ = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
    LAT = Histogram(
        "http_request_duration_seconds",
        "Request duration",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )

    @app.middleware("http")
    async def _metrics_mw(request, call_next):
        route = request.scope.get("route")
        path_tmpl = getattr(route, "path", request.url.path)
        method = request.method
        with LAT.labels(method, path_tmpl).time():
            response = await call_next(request)
        try:
            REQ.labels(method, path_tmpl, str(response.status_code)).inc()
        except Exception:
            pass
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Initialize tracing if configured
    init_tracing(app, default_name="taxi_driver")

    # Trusted hosts + forwarded headers
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or (["*"] if settings.ENV != "prod" else ["api.example.com"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    proxy_trusted = getattr(settings, "PROXY_TRUSTED_IPS", None)
    if proxy_trusted and _ForwardedOrProxy:
        try:
            app.add_middleware(_ForwardedOrProxy, trusted_hosts=proxy_trusted)
        except Exception:
            pass

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
            {"name": "driver", "description": "Driver actions: apply, status, location, profile, earnings"},
            {"name": "taxi_wallet", "description": "Driver's in-app taxi wallet"},
            {"name": "push", "description": "Device push token registration"},
            {"name": "dashboard", "description": "Operator dashboard overview"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
            {"name": "about", "description": "Service information"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
        # Per-route: make selected endpoints unauthenticated
        no_auth_paths = {
            "/", "/docs", "/openapi.json", "/openapi.yaml",
            "/metrics", "/ui", "/health", "/health/deps", "/info",
            "/auth/dev_login_operator",
        }
        for p, ops in openapi_schema.get("paths", {}).items():
            if p in no_auth_paths:
                for op in ops.values():
                    op["security"] = []
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    # Minimal set needed for the Driver app
    app.include_router(auth_router.router)
    app.include_router(driver_router.router)
    app.include_router(taxi_wallet_router.router)
    app.include_router(push_router.router)
    app.include_router(ws_router.router)

    @app.get("/me", tags=["dashboard"])
    def me(user: User = Depends(get_current_user), db = Depends(get_db)):
        if user.role != "driver":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver only")
        drv = db.query(Driver).filter(Driver.user_id == user.id).one_or_none()
        loc = (
            db.query(DriverLocation)
            .filter(DriverLocation.driver_id == drv.id)
            .order_by(DriverLocation.updated_at.desc())
            .first()
        ) if drv else None
        # last active ride
        ride = None
        if drv:
            ride = (
                db.query(Ride)
                .filter(Ride.driver_id == drv.id)
                .order_by(Ride.created_at.desc())
                .first()
            )
        from datetime import datetime, timedelta
        from datetime import timezone
        now = datetime.now(timezone.utc)
        since7 = now - timedelta(days=7)
        since30 = now - timedelta(days=30)
        rides7 = rides30 = earn7 = earn30 = 0
        if drv:
            try:
                from sqlalchemy import func, case, and_, select
                q = select(
                    func.sum(case((and_(Ride.status == "completed", Ride.completed_at >= since7), 1), else_=0)).label("rides7"),
                    func.sum(case((and_(Ride.status == "completed", Ride.completed_at >= since30), 1), else_=0)).label("rides30"),
                    func.coalesce(
                        func.sum(case((and_(Ride.status == "completed", Ride.completed_at >= since7), Ride.final_fare_cents), else_=0)),
                        0,
                    ).label("earn7"),
                    func.coalesce(
                        func.sum(case((and_(Ride.status == "completed", Ride.completed_at >= since30), Ride.final_fare_cents), else_=0)),
                        0,
                    ).label("earn30"),
                ).where(Ride.driver_id == drv.id)
                row = db.execute(q).one()
                rides7 = int(getattr(row, "rides7", 0) or 0)
                rides30 = int(getattr(row, "rides30", 0) or 0)
                earn7 = int(getattr(row, "earn7", 0) or 0)
                earn30 = int(getattr(row, "earn30", 0) or 0)
            except Exception:
                # fallback to zeros if aggregation fails
                rides7 = rides30 = earn7 = earn30 = 0
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name, "role": user.role},
            "driver": None if not drv else {
                "id": str(drv.id),
                "status": drv.status,
                "vehicle_make": drv.vehicle_make,
                "vehicle_plate": drv.vehicle_plate,
            },
            "location": None if not loc else {"lat": loc.lat, "lon": loc.lon, "updated_at": loc.updated_at},
            "last_ride": None if not ride else {"id": str(ride.id), "status": ride.status, "created_at": ride.created_at},
            "metrics": {"7d": {"rides_completed": int(rides7), "earnings_cents": int(earn7)}, "30d": {"rides_completed": int(rides30), "earnings_cents": int(earn30)}},
        }
    @app.get("/health/deps", tags=["health"])
    def health_deps():
        out = {}
        # DB
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("select 1")
            out["db"] = "ok"
        except Exception as e:
            out["db"] = f"error: {e.__class__.__name__}"
        # Redis (optional)
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
        return {"service": "Taxi Driver API", "version": "0.1.0", "env": settings.ENV}

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
        import secrets
        nonce = secrets.token_urlsafe(16)
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
    <h3>Driver</h3>
    <div>
      <input id=\"mk\" placeholder=\"vehicle_make\"> <input id=\"pl\" placeholder=\"vehicle_plate\">
      <button onclick=\"applyDriver()\">Apply</button>
    </div>
    <div>
      <select id=\"dst\"><option>offline</option><option>available</option><option>busy</option></select>
      <button onclick=\"setStatus()\">Set Status</button>
    </div>
    <div>
      <input id=\"lat\" placeholder=\"lat\" style=\"width:120px\">
      <input id=\"lon\" placeholder=\"lon\" style=\"width:120px\">
      <button onclick=\"setLoc()\">Set Location</button>
    </div>
    <div>
      <button onclick=\"profile()\">Profile</button>
      <button onclick=\"ratings()\">Ratings</button>
      <input id=\"days\" type=\"number\" value=\"7\" style=\"width:80px\"> <button onclick=\"earnings()\">Earnings</button>
    </div>
    <pre id=\"dout\"></pre>
  </div>
</div>
<script nonce=\"{nonce}\">
const out=document.getElementById('out');
const dout=document.getElementById('dout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function applyDriver(){ const body={vehicle_make:mk.value, vehicle_plate:pl.value}; const r=await fetch('/driver/apply',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); dout.textContent=await r.text(); }
async function setStatus(){ const body={status: document.getElementById('dst').value}; const r=await fetch('/driver/status',{method:'PUT', headers:auth(true), body: JSON.stringify(body)}); dout.textContent=await r.text(); }
async function setLoc(){ const body={lat: parseFloat(lat.value), lon: parseFloat(lon.value)}; const r=await fetch('/driver/location',{method:'PUT', headers:auth(true), body: JSON.stringify(body)}); dout.textContent=await r.text(); }
async function profile(){ const r=await fetch('/driver/profile',{headers:auth()}); dout.textContent=await r.text(); }
async function ratings(){ const r=await fetch('/driver/ratings',{headers:auth()}); dout.textContent=await r.text(); }
async function earnings(){ const d=parseInt(document.getElementById('days').value||'7',10); const r=await fetch('/driver/earnings?days='+d,{headers:auth()}); dout.textContent=await r.text(); }
</script>
"""
        resp = PlainTextResponse(html, media_type="text/html; charset=utf-8")
        try:
            resp.headers["Content-Security-Policy"] = f"script-src 'self' 'nonce-{nonce}'"
        except Exception:
            pass
        return resp

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
