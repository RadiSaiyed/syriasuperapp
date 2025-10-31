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

# Import Agriculture domain via PYTHONPATH=apps/agriculture
from app.config import settings
from app.database import engine
from app.models import Base
from app.middleware_request_id import RequestIDMiddleware
from app.middleware_rate_limit import SlidingWindowLimiter, RedisRateLimiter
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
from operators._shared.common import SecurityHeadersMiddleware, init_tracing
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

from app.routers import auth as auth_router
from app.routers import farmer as farmer_router
from app.auth import get_current_user
from app.database import get_db
from app.models import Farm, Listing, Order
from fastapi import HTTPException, status, Depends


def create_app() -> FastAPI:
    app = FastAPI(title="Agriculture Farmer API", version="0.1.0")

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

    # Optional: auto-create schema
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
    init_tracing(app, default_name="agriculture_farmer")

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
            {"name": "farmer", "description": "Manage farm, listings and orders"},
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
    app.include_router(farmer_router.router)
    
    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Agriculture Farmer API", "version": "0.1.0", "env": settings.ENV}
    
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
    <h3>Farm + Listings + Jobs</h3>
    <div>
      <input id=\"fname\" placeholder=\"farm name\"> <input id=\"floc\" placeholder=\"location\"> <input id=\"fdesc\" placeholder=\"description\" size=\"32\">
      <button onclick=\"createFarm()\">Create Farm</button>
      <button onclick=\"getFarm()\">Get Farm</button>
    </div>
    <div>
      <input id=\"prod\" placeholder=\"produce_name\"> <input id=\"cat\" placeholder=\"category\"> <input id=\"qty\" type=\"number\" placeholder=\"qty_kg\" style=\"width:100px\"> <input id=\"ppkg\" type=\"number\" placeholder=\"price_per_kg_cents\" style=\"width:140px\">
      <button onclick=\"createListing()\">Create Listing</button>
      <button onclick=\"listListings()\">My Listings</button>
    </div>
    <div>
      <input id=\"jtitle\" placeholder=\"job title\"> <input id=\"jloc\" placeholder=\"location\"> <input id=\"jw\" type=\"number\" placeholder=\"wage_per_day_cents\" style=\"width:160px\"> <input id=\"js\" placeholder=\"start_date YYYY-MM-DD\"> <input id=\"je\" placeholder=\"end_date YYYY-MM-DD\">
      <button onclick=\"createJob()\">Create Job</button>
      <button onclick=\"listJobs()\">My Jobs</button>
    </div>
    <div>
      <input id=\"jobid\" placeholder=\"job_id\" size=\"36\"> <button onclick=\"listApps()\">Applications</button>
      <input id=\"appid\" placeholder=\"application_id\" size=\"36\"> <select id=\"appst\"><option>applied</option><option>reviewed</option><option>accepted</option><option>rejected</option></select> <button onclick=\"setAppStatus()\">Set Status</button>
    </div>
    <div>
      <button onclick=\"listOrders()\">Orders</button>
    </div>
    <pre id=\"fout\"></pre>
  </div>
</div>
<script>
const out=document.getElementById('out');
const fout=document.getElementById('fout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function createFarm(){ const body={name:fname.value, location:floc.value, description:fdesc.value}; const r=await fetch('/farmer/farm',{method:'POST',headers:auth(true),body:JSON.stringify(body)}); fout.textContent=await r.text(); }
async function getFarm(){ const r=await fetch('/farmer/farm',{headers:auth()}); fout.textContent=await r.text(); }
async function createListing(){ const body={produce_name:prod.value, category:cat.value, quantity_kg:parseInt(qty.value||'0',10), price_per_kg_cents:parseInt(ppkg.value||'0',10)}; const r=await fetch('/farmer/listings',{method:'POST',headers:auth(true),body:JSON.stringify(body)}); fout.textContent=await r.text(); }
async function listListings(){ const r=await fetch('/farmer/listings',{headers:auth()}); fout.textContent=await r.text(); }
async function createJob(){ const body={title:jtitle.value, description:'', location:jloc.value, wage_per_day_cents:parseInt(jw.value||'0',10), start_date:js.value, end_date:je.value}; const r=await fetch('/farmer/jobs',{method:'POST',headers:auth(true),body:JSON.stringify(body)}); fout.textContent=await r.text(); }
async function listJobs(){ const r=await fetch('/farmer/jobs',{headers:auth()}); fout.textContent=await r.text(); }
async function listApps(){ const id=document.getElementById('jobid').value.trim(); const r=await fetch('/farmer/jobs/'+id+'/applications',{headers:auth()}); fout.textContent=await r.text(); }
async function setAppStatus(){ const id=document.getElementById('appid').value.trim(); const st=document.getElementById('appst').value; const body={status:st}; const r=await fetch('/farmer/applications/'+id,{method:'PATCH',headers:auth(true),body:JSON.stringify(body)}); fout.textContent=await r.text(); }
async function listOrders(){ const r=await fetch('/farmer/orders',{headers:auth()}); fout.textContent=await r.text(); }
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
    
    @app.get("/me", tags=["dashboard"])
    def me(user = Depends(get_current_user), db = Depends(get_db)):
        if user.role != "farmer":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmer only")
        farm = db.query(Farm).filter(Farm.owner_user_id == user.id).one_or_none()
        listings = db.query(Listing).filter(Listing.farm_id == (farm.id if farm else None)).count() if farm else 0
        orders = 0
        if farm:
            listing_ids = [l.id for l in db.query(Listing).filter(Listing.farm_id == farm.id).all()]
            if listing_ids:
                orders = db.query(Order).filter(Order.listing_id.in_(listing_ids)).count()
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        o7 = o30 = 0
        if farm:
            if listing_ids:
                o7 = db.query(Order).filter(Order.listing_id.in_(listing_ids), Order.created_at >= since7).count()
                o30 = db.query(Order).filter(Order.listing_id.in_(listing_ids), Order.created_at >= since30).count()
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name},
            "farm": None if not farm else {"id": str(farm.id), "name": farm.name},
            "listings_total": int(listings),
            "orders_total": int(orders),
            "metrics": {"7d": {"orders_total": int(o7)}, "30d": {"orders_total": int(o30)}},
        }
    return app


app = create_app()
