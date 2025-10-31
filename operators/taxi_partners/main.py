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
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

# Import Taxi domain via PYTHONPATH=apps/taxi
from app.config import settings
from app.database import engine
from app.models import Base
from app.middleware_request_id import RequestIDMiddleware
from app.middleware_rate_limit import SlidingWindowLimiter
from app.middleware_rate_limit_redis import RedisRateLimiter
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
from superapp_shared.internal_hmac import sign_internal_request_headers
import httpx, os
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

from app.routers import auth as auth_router
from app.routers import partners as partners_router
from operators._shared.common import SecurityHeadersMiddleware, init_tracing


def create_app() -> FastAPI:
    app = FastAPI(title="Taxi Partners API", version="0.1.0")

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

    # Request ID + Security headers + compression
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)

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
    init_tracing(app, default_name="taxi_partners")

    # Trusted hosts + forwarded headers
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or (["*"] if settings.ENV != "prod" else ["api.example.com"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    proxy_trusted = getattr(settings, "PROXY_TRUSTED_IPS", None)
    if proxy_trusted and _ForwardedOrProxy:
        try:
            app.add_middleware(_ForwardedOrProxy, trusted_hosts=proxy_trusted)
        except Exception:
            pass

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
            {"name": "partners", "description": "Partner admin + webhooks for external dispatch"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
            {"name": "about", "description": "Service information"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
        # Allow unauthenticated access to selected endpoints
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

    app.include_router(auth_router.router)
    app.include_router(partners_router.router)
    
    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Taxi Partners API", "version": "0.1.0", "env": settings.ENV}
    
    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml():
        spec = app.openapi()
        try:
            import yaml  # type: ignore
            return PlainTextResponse(yaml.safe_dump(spec, sort_keys=False), media_type="application/yaml")
        except Exception:
            import json as _json
            return PlainTextResponse(_json.dumps(spec, indent=2), media_type="application/yaml")
    
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
      <button onclick=\"info()\">/info</button>
      <button onclick=\"health()\">/health</button>
      <a href=\"/docs\" target=\"_blank\">/docs</a>
      <a href=\"/openapi.yaml\" target=\"_blank\">/openapi.yaml</a>
    </div>
    <pre id=\"out\"></pre>
  </div>
  <div class=\"card\">
    <h3>Dev + Dispatch</h3>
    <div>
      <input id=\"pname\" placeholder=\"partner name\"> <input id=\"pkey\" placeholder=\"key_id\"> <input id=\"psec\" placeholder=\"secret\"> <button onclick=\"regPartner()\">Register Partner</button>
    </div>
    <div>
      <input id=\"ekey\" placeholder=\"partner_key_id\"> <input id=\"ext\" placeholder=\"external_driver_id\"> <input id=\"dphone\" placeholder=\"driver_phone\"> <button onclick=\"mapDriver()\">Map Driver</button>
    </div>
    <div>
      <input id=\"rid\" placeholder=\"ride_id\" size=\"36\"> <input id=\"k2\" placeholder=\"partner_key_id\"> <input id=\"trip\" placeholder=\"external_trip_id (opt)\"> <button onclick=\"dispatch()\">Create Dispatch</button>
    </div>
    <div>
      <h4>Simulate Webhooks → Taxi</h4>
      <div class=\"small\">Taxi Base (optional, default http://localhost:8081)</div>
      <input id=\"taxi_base\" size=\"36\" placeholder=\"http://localhost:8081\">
      <div>Ride Status: <input id=\"wh_key\" placeholder=\"partner_key_id\"> <input id=\"wh_trip\" placeholder=\"external_trip_id\"> <select id=\"wh_status\"><option>accepted</option><option>enroute</option><option>completed</option><option>canceled</option></select> <input id=\"wh_fare\" type=\"number\" placeholder=\"final_fare_cents (opt)\"> <button onclick=\"sendRideStatus()\">Send</button></div>
      <div>Driver Location: <input id=\"wh_key2\" placeholder=\"partner_key_id\"> <input id=\"wh_drv\" placeholder=\"external_driver_id\"> <input id=\"wh_lat\" placeholder=\"lat\" style=\"width:100px\"> <input id=\"wh_lon\" placeholder=\"lon\" style=\"width:100px\"> <button onclick=\"sendDriverLoc()\">Send</button></div>
    </div>
    <pre id=\"pout\"></pre>
  </div>
</div>
<script nonce=\"{nonce}\">
const out=document.getElementById('out');
const pout=document.getElementById('pout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function regPartner(){ const body={name:pname.value, key_id:pkey.value, secret:psec.value}; const r=await fetch('/partners/dev/register',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); pout.textContent=await r.text(); }
async function mapDriver(){ const body={partner_key_id:ekey.value, external_driver_id:ext.value, driver_phone:dphone.value}; const r=await fetch('/partners/dev/map_driver',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); pout.textContent=await r.text(); }
async function dispatch(){ const body={ride_id:rid.value, partner_key_id:k2.value, external_trip_id:trip.value||null}; const r=await fetch('/partners/dispatch',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); pout.textContent=await r.text(); }
async function sendRideStatus(){ const base=(document.getElementById('taxi_base').value||'').trim(); const body={partner_key_id: (document.getElementById('wh_key').value||document.getElementById('k2').value||''), external_trip_id: document.getElementById('wh_trip').value, status: document.getElementById('wh_status').value, final_fare_cents: document.getElementById('wh_fare').value?parseInt(document.getElementById('wh_fare').value,10):null, base: base||null}; const r=await fetch('/dev/sim_webhook/ride_status',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); pout.textContent=await r.text(); }
async function sendDriverLoc(){ const base=(document.getElementById('taxi_base').value||'').trim(); const body={partner_key_id: (document.getElementById('wh_key2').value||document.getElementById('k2').value||''), external_driver_id: document.getElementById('wh_drv').value, lat: parseFloat(document.getElementById('wh_lat').value||'0'), lon: parseFloat(document.getElementById('wh_lon').value||'0'), base: base||null}; const r=await fetch('/dev/sim_webhook/driver_location',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); pout.textContent=await r.text(); }
</script>
"""
        resp = PlainTextResponse(html, media_type="text/html; charset=utf-8")
        try:
            resp.headers["Content-Security-Policy"] = f"script-src 'self' 'nonce-{nonce}'"
        except Exception:
            pass
        return resp
    # Dev helper endpoints to simulate HMAC webhooks to Taxi API
    @app.post("/dev/sim_webhook/ride_status", tags=["dev"])
    def sim_ride_status(partner_key_id: str, external_trip_id: str, status: str, final_fare_cents: int | None = None, base: str | None = None, db = Depends(get_db)):
        _db = next(db())
        try:
            from app.models import Partner
            p = _db.query(Partner).filter(Partner.key_id == partner_key_id).one_or_none()
            if p is None:
                raise HTTPException(status_code=404, detail="partner_not_found")
            payload = {"external_trip_id": external_trip_id, "status": status}
            if final_fare_cents is not None:
                payload["final_fare_cents"] = int(final_fare_cents)
            headers = sign_internal_request_headers(payload, p.secret)
            taxi_base = (base or os.getenv("TAXI_BASE", "http://localhost:8081")).rstrip("/")
            url = f"{taxi_base}/partners/{partner_key_id}/webhooks/ride_status"
            r = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            return {"status_code": r.status_code, "body": r.text}
        finally:
            _db.close()

    @app.post("/dev/sim_webhook/driver_location", tags=["dev"])
    def sim_driver_location(partner_key_id: str, external_driver_id: str, lat: float, lon: float, base: str | None = None, db = Depends(get_db)):
        _db = next(db())
        try:
            from app.models import Partner
            p = _db.query(Partner).filter(Partner.key_id == partner_key_id).one_or_none()
            if p is None:
                raise HTTPException(status_code=404, detail="partner_not_found")
            payload = {"external_driver_id": external_driver_id, "lat": float(lat), "lon": float(lon)}
            headers = sign_internal_request_headers(payload, p.secret)
            taxi_base = (base or os.getenv("TAXI_BASE", "http://localhost:8081")).rstrip("/")
            url = f"{taxi_base}/partners/{partner_key_id}/webhooks/driver_location"
            r = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            return {"status_code": r.status_code, "body": r.text}
        finally:
            _db.close()

    return app


app = create_app()
