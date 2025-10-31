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

# Import Stays domain via PYTHONPATH=apps/stays
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
from app.routers import host as host_router
from app.auth import get_current_user
from app.database import get_db
from app.models import User, Property, Unit, Reservation
from fastapi import HTTPException, status, Depends


def create_app() -> FastAPI:
    app = FastAPI(title="Stays Host API", version="0.1.0")

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

    init_tracing(app, default_name="stays_host")

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
            {"name": "host", "description": "Host endpoints: properties, units, reservations"},
            {"name": "dashboard", "description": "Operator dashboard overview"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
            {"name": "about", "description": "Service information"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
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
    app.include_router(host_router.router)

    @app.get("/me", tags=["dashboard"])
    def me(user: User = Depends(get_current_user), db = Depends(get_db)):
        if user.role != "host":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host only")
        props = db.query(Property).filter(Property.owner_user_id == user.id).count()
        units = db.query(Unit).join(Property, Property.id == Unit.property_id).filter(Property.owner_user_id == user.id).count()
        resv = db.query(Reservation).join(Unit, Unit.id == Reservation.unit_id).join(Property, Property.id == Unit.property_id).filter(Property.owner_user_id == user.id).count()
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        r7 = db.query(Reservation).join(Unit, Unit.id == Reservation.unit_id).join(Property, Property.id == Unit.property_id).filter(Property.owner_user_id == user.id, Reservation.created_at >= since7).count()
        r30 = db.query(Reservation).join(Unit, Unit.id == Reservation.unit_id).join(Property, Property.id == Unit.property_id).filter(Property.owner_user_id == user.id, Reservation.created_at >= since30).count()
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name},
            "properties_total": int(props),
            "units_total": int(units),
            "reservations_total": int(resv),
            "metrics": {"7d": {"reservations_total": int(r7)}, "30d": {"reservations_total": int(r30)}},
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
        return {"service": "Stays Host API", "version": "0.1.0", "env": settings.ENV}
    
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
  button,input,select,textarea{{font-size:14px;margin:4px;padding:6px 8px}}
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
    <h3>Host</h3>
    <div>
      <input id=\"pname\" placeholder=\"property name\"> <input id=\"pcity\" placeholder=\"city\"> <button onclick=\"createProperty()\">Create Property</button> <button onclick=\"listProperties()\">My Properties</button>
    </div>
    <div>
      <input id=\"pid\" placeholder=\"property_id\" size=\"36\"> <input id=\"uname\" placeholder=\"unit name\"> <input id=\"cap\" type=\"number\" placeholder=\"capacity\" style=\"width:100px\"> <input id=\"tu\" type=\"number\" placeholder=\"total_units\" style=\"width:120px\"> <input id=\"np\" type=\"number\" placeholder=\"price_cents_per_night\" style=\"width:200px\"> <button onclick=\"addUnit()\">Add Unit</button> <button onclick=\"listUnits()\">List Units</button>
    </div>
    <div>
      <button onclick=\"listResv()\">Reservations</button> <input id=\"rid\" placeholder=\"reservation_id\" size=\"36\"> <button onclick=\"confirmResv()\">Confirm</button> <button onclick=\"cancelResv()\">Cancel</button>
    </div>
    <div>
      <h4>Images</h4>
      <input id=\"img_pid\" placeholder=\"property_id\" size=\"36\"> <input id=\"img_url\" placeholder=\"image URL\" size=\"36\"> <input id=\"img_sort\" type=\"number\" placeholder=\"sort_order\" style=\"width:120px\"> <button onclick=\"addImage()\">Add</button> <button onclick=\"listImages()\">List</button> <input id=\"img_id\" placeholder=\"image_id\" size=\"36\"> <button onclick=\"delImage()\">Delete</button>
    </div>
    <div>
      <h4>Blocks</h4>
      <input id=\"unit_id\" placeholder=\"unit_id\" size=\"36\"> <input id=\"blk_s\" placeholder=\"start YYYY-MM-DD\"> <input id=\"blk_e\" placeholder=\"end YYYY-MM-DD\"> <input id=\"blk_n\" type=\"number\" placeholder=\"blocked_units\" style=\"width:160px\"> <button onclick=\"addBlock()\">Add</button> <button onclick=\"listBlocks()\">List</button> <input id=\"block_id\" placeholder=\"block_id\" size=\"36\"> <button onclick=\"delBlock()\">Delete</button>
    </div>
    <div>
      <h4>Prices</h4>
      <input id=\"price_unit\" placeholder=\"unit_id\" size=\"36\"> <input id=\"price_date\" placeholder=\"date YYYY-MM-DD\"> <input id=\"price_amt\" type=\"number\" placeholder=\"price_cents\" style=\"width:160px\"> <button onclick=\"setPrice()\">Set</button> <button onclick=\"getPrices()\">Get</button>
    </div>
    <pre id=\"hout\"></pre>
  </div>
</div>
<script>
const out=document.getElementById('out');
const hout=document.getElementById('hout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function createProperty(){ const body={name:pname.value, type:'apartment', city:pcity.value}; const r=await fetch('/host/properties',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); hout.textContent=await r.text(); }
async function listProperties(){ const r=await fetch('/host/properties',{headers:auth()}); hout.textContent=await r.text(); }
async function addUnit(){ const pid=document.getElementById('pid').value.trim(); const body={name:uname.value, capacity:parseInt(cap.value||'1',10), total_units:parseInt(tu.value||'1',10), price_cents_per_night:parseInt(np.value||'0',10)}; const r=await fetch('/host/properties/'+pid+'/units',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); hout.textContent=await r.text(); }
async function listUnits(){ const pid=document.getElementById('pid').value.trim(); const r=await fetch('/host/properties/'+pid+'/units',{headers:auth()}); hout.textContent=await r.text(); }
async function listResv(){ const r=await fetch('/host/reservations',{headers:auth()}); hout.textContent=await r.text(); }
async function confirmResv(){ const id=document.getElementById('rid').value.trim(); const r=await fetch('/host/reservations/'+id+'/confirm',{method:'POST', headers:auth()}); hout.textContent=await r.text(); }
async function cancelResv(){ const id=document.getElementById('rid').value.trim(); const r=await fetch('/host/reservations/'+id+'/cancel',{method:'POST', headers:auth()}); hout.textContent=await r.text(); }
async function addImage(){ const pid=document.getElementById('img_pid').value.trim(); const body=[{url: document.getElementById('img_url').value, sort_order: parseInt(document.getElementById('img_sort').value||'0',10)}]; const r=await fetch('/host/properties/'+pid+'/images',{method:'POST', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); hout.textContent=await r.text(); }
async function listImages(){ const pid=document.getElementById('img_pid').value.trim(); const r=await fetch('/host/properties/'+pid+'/images',{headers:auth()}); hout.textContent=await r.text(); }
async function delImage(){ const id=document.getElementById('img_id').value.trim(); const r=await fetch('/host/images/'+id,{method:'DELETE', headers:auth()}); hout.textContent=await r.text(); }
async function addBlock(){ const uid=document.getElementById('unit_id').value.trim(); const body={start_date: blk_s.value, end_date: blk_e.value, blocked_units: parseInt(blk_n.value||'1',10)}; const r=await fetch('/host/units/'+uid+'/blocks',{method:'POST', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); hout.textContent=await r.text(); }
async function listBlocks(){ const uid=document.getElementById('unit_id').value.trim(); const r=await fetch('/host/units/'+uid+'/blocks',{headers:auth()}); hout.textContent=await r.text(); }
async function delBlock(){ const id=document.getElementById('block_id').value.trim(); const r=await fetch('/host/blocks/'+id,{method:'DELETE', headers:auth()}); hout.textContent=await r.text(); }
async function setPrice(){ const uid=document.getElementById('price_unit').value.trim(); const body=[{date: price_date.value, price_cents: parseInt(price_amt.value||'0',10)}]; const r=await fetch('/host/units/'+uid+'/prices',{method:'PUT', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); hout.textContent=await r.text(); }
async function getPrices(){ const uid=document.getElementById('price_unit').value.trim(); const r=await fetch('/host/units/'+uid+'/prices',{headers:auth()}); hout.textContent=await r.text(); }
</script>
"""
        import secrets
        nonce = secrets.token_urlsafe(16)
        html = html.replace("<script>", f"<script nonce=\"{nonce}\">", 1)
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
