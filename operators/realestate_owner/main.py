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

# Import Realestate domain pieces via PYTHONPATH=apps/realestate
from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import owner as owner_router
from app.auth import ensure_user, _make_token, _verify_dev_otp
from app.schemas import TokenOut, RequestOtpIn, VerifyOtpIn
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
from operators._shared.common import SecurityHeadersMiddleware, init_tracing
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None
from app.database import get_db
from app.auth import get_current_user
from app.models import Listing, Reservation


def create_app() -> FastAPI:
    app = FastAPI(title="Real Estate Owner API", version="0.1.0", docs_url="/docs")

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
    # Security headers + tracing
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(SecurityHeadersMiddleware)
    init_tracing(app, default_name="realestate_owner")

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
            {"name": "owner", "description": "Owner endpoints: listings and reservations"},
            {"name": "dashboard", "description": "Operator dashboard overview"},
            {"name": "health", "description": "Liveness/readiness and dependencies"},
            {"name": "about", "description": "Service information"},
        ]
        comps = openapi_schema.setdefault("components", {})
        security_schemes = comps.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        openapi_schema["security"] = [{"HTTPBearer": []}]
        openapi_schema["tags"] = tags_meta
        # Public endpoints unauthenticated
        no_auth_paths = {
            "/", "/docs", "/openapi.json", "/openapi.yaml",
            "/metrics", "/ui", "/health", "/health/deps", "/info",
            "/auth/request_otp", "/auth/verify_otp", 
            "/auth/dev_login_operator",
        }
        for p, ops in openapi_schema.get("paths", {}).items():
            if p in no_auth_paths:
                for op in ops.values():
                    op["security"] = []
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    # Minimal auth endpoints (replicates service's main logic)
    DISABLE_OTP = settings.DEV_MODE and getattr(settings, "DEV_DISABLE_OTP", False)

    @app.post("/auth/request_otp", tags=["auth"], include_in_schema=not DISABLE_OTP)
    def request_otp(payload: RequestOtpIn):
        if DISABLE_OTP:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        return {"detail": "otp_sent"}

    @app.post("/auth/verify_otp", response_model=TokenOut, tags=["auth"], include_in_schema=not DISABLE_OTP)
    def verify_otp(payload: VerifyOtpIn):
        if DISABLE_OTP:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        if not _verify_dev_otp(payload.phone, payload.otp):
            from fastapi import HTTPException, status as _status
            raise HTTPException(status_code=_status.HTTP_400_BAD_REQUEST, detail="invalid_otp")
        from app.database import get_db
        db = next(get_db())
        try:
            u = ensure_user(db, payload.phone, payload.name)
            token = _make_token(str(u.id))
        finally:
            db.close()
        return TokenOut(access_token=token)

    # Dev-only username/password login mirroring service defaults
    from pydantic import BaseModel

    class DevLoginIn(BaseModel):
        username: str
        password: str

    @app.post("/auth/dev_login", response_model=TokenOut, tags=["auth"])
    def dev_login(payload: DevLoginIn):
        if settings.ENV.lower() != "dev":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        users = {
            "admin": {"password": "admin", "phone": "+963901000001", "name": "Admin"},
            "superuser": {"password": "super", "phone": "+963901000002", "name": "Super User"},
            "user1": {"password": "user", "phone": "+963996428955", "name": "User One"},
            "user2": {"password": "user", "phone": "+963996428996", "name": "User Two"},
        }
        u = users.get(payload.username.lower())
        if not u or payload.password != u["password"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        db = next(get_db())
        try:
            usr = ensure_user(db, u["phone"], u.get("name"))
            token = _make_token(str(usr.id))
        finally:
            db.close()
        return TokenOut(access_token=token)

    app.include_router(owner_router.router)
    # Compression
    app.add_middleware(GZipMiddleware, minimum_size=500)

    @app.get("/me", tags=["dashboard"])
    def me(user = Depends(get_current_user), db = Depends(get_db)):
        listings = db.query(Listing).filter(Listing.owner_phone == user.phone).count()
        resv = db.query(Reservation).filter(Reservation.owner_phone == user.phone).count()
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        l7 = db.query(Listing).filter(Listing.owner_phone == user.phone).filter(Listing.created_at >= since7).count()
        l30 = db.query(Listing).filter(Listing.owner_phone == user.phone).filter(Listing.created_at >= since30).count()
        r7 = db.query(Reservation).filter(Reservation.owner_phone == user.phone, Reservation.created_at >= since7).count()
        r30 = db.query(Reservation).filter(Reservation.owner_phone == user.phone, Reservation.created_at >= since30).count()
        return {"user": {"id": str(user.id), "phone": user.phone, "name": user.name}, "listings_total": int(listings), "reservations_total": int(resv), "metrics": {"7d": {"listings_total": int(l7), "reservations_total": int(r7)}, "30d": {"listings_total": int(l30), "reservations_total": int(r30)}}}
    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Real Estate Owner API", "version": "0.1.0", "env": settings.ENV}
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
                "info": "/info",
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
    <h3>Owner</h3>
    <div>
      <input id=\"ltitle\" placeholder=\"title\"> <input id=\"lcity\" placeholder=\"city\"> <input id=\"ltype\" placeholder=\"type rent|sale\" style=\"width:140px\"> <input id=\"lpt\" placeholder=\"property_type\" style=\"width:140px\"> <input id=\"lprice\" type=\"number\" placeholder=\"price_cents\"> <button onclick=\"createListing()\">Create Listing</button>
    </div>
    <div>
      <button onclick=\"listings()\">My Listings</button>
      <input id=\"lid\" placeholder=\"listing_id\" size=\"36\"> <input id=\"ntitle\" placeholder=\"new title\"> <button onclick=\"updateListing()\">Update</button>
    </div>
    <div>
      <button onclick=\"reservations()\">Reservations</button> <input id=\"rid\" placeholder=\"reservation_id\" size=\"36\"> <select id=\"dec\"><option>accepted</option><option>rejected</option></select> <button onclick=\"decide()\">Decide</button>
    </div>
    <pre id=\"oout\"></pre>
  </div>
</div>
<script nonce=\"{nonce}\">
const out=document.getElementById('out');
const oout=document.getElementById('oout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function createListing(){ const body=new URLSearchParams(); body.append('title',ltitle.value); body.append('city',lcity.value); body.append('type',ltype.value||'rent'); body.append('property_type',lpt.value||'apartment'); body.append('price_cents', String(parseInt(lprice.value||'0',10))); const r=await fetch('/owner/listings',{method:'POST', headers:auth(), body}); oout.textContent=await r.text(); }
async function listings(){ const r=await fetch('/owner/listings',{headers:auth()}); oout.textContent=await r.text(); }
async function updateListing(){ const id=document.getElementById('lid').value.trim(); const body=new URLSearchParams(); if(ntitle.value) body.append('title', ntitle.value); const r=await fetch('/owner/listings/'+id,{method:'PATCH', headers:auth(), body}); oout.textContent=await r.text(); }
async function reservations(){ const r=await fetch('/owner/reservations',{headers:auth()}); oout.textContent=await r.text(); }
async function decide(){ const id=document.getElementById('rid').value.trim(); const body=new URLSearchParams(); body.append('decision', document.getElementById('dec').value); const r=await fetch('/owner/reservations/'+id+'/decision',{method:'POST', headers:auth(), body}); oout.textContent=await r.text(); }
</script>
"""
        resp = PlainTextResponse(html, media_type="text/html; charset=utf-8")
        try:
            resp.headers["Content-Security-Policy"] = f"script-src 'self' 'nonce-{nonce}'"
        except Exception:
            pass
        return resp
    return app


app = create_app()
