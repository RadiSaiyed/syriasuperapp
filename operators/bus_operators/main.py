from fastapi import FastAPI, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
try:
    from starlette.middleware.forwarded import ForwardedMiddleware as _ForwardedOrProxy  # Starlette >=0.37
except Exception:  # fallback for older Starlette
    try:
        from starlette.middleware.proxy_headers import ProxyHeadersMiddleware as _ForwardedOrProxy  # type: ignore
    except Exception:  # pragma: no cover - if neither is available
        _ForwardedOrProxy = None  # type: ignore
from sqlalchemy import text, func, select, case

# Import Bus domain app primitives via PYTHONPATH=apps/bus
from app.config import settings
from app.database import engine
from app.models import Base
from app.middleware_request_id import RequestIDMiddleware
from app.middleware_rate_limit import SlidingWindowLimiter
from app.middleware_rate_limit_redis import RedisRateLimiter
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse
import json
import os
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

from app.routers import auth as auth_router
from app.routers import operators as operators_router
from app.auth import get_current_user, create_access_token
from app.database import get_db
from app.models import User, Operator, OperatorMember, Trip, Booking
from app.schemas import TokenOut
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from operators._shared.common import SecurityHeadersMiddleware, init_tracing


def create_app() -> FastAPI:
    app = FastAPI(title="Bus Operators API", version="0.1.0")

    # Optional Sentry init
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn and sentry_sdk is not None:
        try:
            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")))
        except Exception:
            pass

    # CORS: avoid browsers blocking preflights when using credentials with '*'
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
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # Trusted hosts: limit Host header to expected values (behind proxies/load balancers)
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or (["*"] if settings.ENV != "prod" else ["api.example.com"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Forwarded/Proxy headers: respect X-Forwarded-* / Forwarded when trusted proxies are configured
    proxy_trusted = getattr(settings, "PROXY_TRUSTED_IPS", None)
    if proxy_trusted and _ForwardedOrProxy:
        try:
            app.add_middleware(_ForwardedOrProxy, trusted_hosts=proxy_trusted)  # type: ignore[arg-type]
        except Exception:
            pass

    # Request ID + JSON logs
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
    init_tracing(app, default_name="bus_operators")

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
            {"name": "operators", "description": "Bus operators management and operations"},
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
    app.include_router(operators_router.router)

    class DevLoginIn(BaseModel):
        username: str
        password: str

    @app.post("/auth/dev_login_operator", response_model=TokenOut, tags=["auth"])
    def dev_login_operator(payload: DevLoginIn, db: Session = Depends(get_db)):
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
        created = False
        user = db.query(User).filter(User.phone == u["phone"]).one_or_none()
        if user is None:
            user = User(phone=u["phone"], name=u.get("name"))
            db.add(user)
            db.flush()
            created = True
        # Ensure at least one operator and membership
        op = db.query(Operator).order_by(Operator.created_at.asc()).first()
        if op is None:
            op = Operator(name="Dev Operator")
            db.add(op)
            db.flush()
            created = True
        mem = (
            db.query(OperatorMember)
            .filter(OperatorMember.operator_id == op.id, OperatorMember.user_id == user.id)
            .one_or_none()
        )
        if mem is None:
            mem = OperatorMember(operator_id=op.id, user_id=user.id, role="admin")
            db.add(mem)
            db.flush()
            created = True
        if created:
            try:
                db.commit()
            except Exception:
                db.rollback()
        token = create_access_token(str(user.id), user.phone)
        return TokenOut(access_token=token)

    @app.get("/me", tags=["dashboard"])
    def me(user: User = Depends(get_current_user), db = Depends(get_db)):
        mems = (
            db.query(OperatorMember, Operator)
            .join(Operator, Operator.id == OperatorMember.operator_id)
            .filter(OperatorMember.user_id == user.id)
            .all()
        )
        if not mems:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an operator member")
        op_summaries = []
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        # Aggregate counts in batch per operator to avoid N+1 queries
        op_ids = [op.id for (_mem, op) in mems]
        trips_per_op = {}
        if op_ids:
            rows = db.execute(
                select(Trip.operator_id, func.count(Trip.id)).where(Trip.operator_id.in_(op_ids)).group_by(Trip.operator_id)
            ).all()
            trips_per_op = {row[0]: int(row[1] or 0) for row in rows}
            b_rows = db.execute(
                select(
                    Trip.operator_id.label("op_id"),
                    func.count(Booking.id).label("total"),
                    func.sum(case((Booking.created_at >= since7, 1), else_=0)).label("b7"),
                    func.sum(case((Booking.created_at >= since30, 1), else_=0)).label("b30"),
                )
                .join(Trip, Trip.id == Booking.trip_id)
                .where(Trip.operator_id.in_(op_ids))
                .group_by(Trip.operator_id)
            ).all()
            bkg_by_op = {row.op_id: row for row in b_rows}
        else:
            bkg_by_op = {}
        for mem, op in mems:
            trips = trips_per_op.get(op.id, 0)
            bc = bkg_by_op.get(op.id)
            b_total = int(getattr(bc, "total", 0) or 0)
            b7 = int(getattr(bc, "b7", 0) or 0)
            b30 = int(getattr(bc, "b30", 0) or 0)
            op_summaries.append({
                "operator_id": str(op.id),
                "operator_name": op.name,
                "role": mem.role,
                "trips_total": int(trips),
                "bookings_total": b_total,
                "metrics": {"7d": {"bookings_total": b7}, "30d": {"bookings_total": b30}},
            })
        return {"user": {"id": str(user.id), "phone": user.phone, "name": user.name}, "operators": op_summaries}
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
        return {"service": "Bus Operators API", "version": "0.1.0", "env": settings.ENV}
    
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
    <h3>Operator</h3>
    <div>
      <label>Operator ID</label>
      <input id=\"opid\" size=\"40\" placeholder=\"operator UUID\">
      <label>Since days</label>
      <input id=\"since\" type=\"number\" value=\"7\" style=\"width:80px\">
    </div>
    <div>
      <button onclick=\"listTrips()\">Trips</button>
      <button onclick=\"summary()\">Report Summary</button>
      <button onclick=\"manifest()\">Trip Manifest</button>
      <a id=\"csv\" href=\"#\" target=\"_blank\">Bookings CSV</a>
      <input id=\"trip_id\" size=\"36\" placeholder=\"trip UUID (for manifest)\">
      <select id=\"csv_status\"><option value=\"\">all</option><option>confirmed</option><option>canceled</option></select>
      <button onclick=\"updateCSV()\">CSV Link</button>
    </div>
    <pre id=\"opout\"></pre>
  </div>
  <div class=\"card\">
    <h3>Tickets & Clone</h3>
    <div>
      <label>QR</label> <input id=\"qr\" size=\"44\" placeholder=\"BUS|<booking_id>\"> <button onclick=\"validateQR()\">Validate</button>
    </div>
    <div>
      <label>Booking ID</label> <input id=\"bid\" size=\"36\" placeholder=\"booking_id\"> <button onclick=\"board()\">Board</button>
    </div>
    <div>
      <label>Clone Trip</label> <input id=\"src_trip\" size=\"36\" placeholder=\"src trip_id\">
      <input id=\"start\" placeholder=\"start YYYY-MM-DD\" style=\"width:160px\">
      <input id=\"end\" placeholder=\"end YYYY-MM-DD\" style=\"width:160px\">
      <input id=\"wds\" placeholder=\"weekdays (e.g. 0,2,4)\" style=\"width:180px\">
      <button onclick=\"cloneTrip()\">Clone</button>
    </div>
    <pre id=\"tkt\"></pre>
  </div>
  <div class=\"card\">
    <h3>Branches</h3>
    <div>
      <button onclick=\"listBranches()\">List</button>
      <input id=\"br_name\" placeholder=\"name\"> <input id=\"br_fee\" type=\"number\" placeholder=\"commission_bps\" style=\"width:160px\"> <button onclick=\"createBranch()\">Create</button>
    </div>
    <div>
      <input id=\"br_id\" size=\"36\" placeholder=\"branch_id\"> <input id=\"br_name2\" placeholder=\"name\"> <input id=\"br_fee2\" type=\"number\" placeholder=\"commission_bps\" style=\"width:160px\"> <button onclick=\"updateBranch()\">Update</button> <button onclick=\"deleteBranch()\">Delete</button>
    </div>
    <pre id=\"brout\"></pre>
  </div>
  <div class=\"card\">
    <h3>Vehicles</h3>
    <div>
      <button onclick=\"listVehicles()\">List</button>
      <input id=\"vh_name\" placeholder=\"name\"> <input id=\"vh_seats\" type=\"number\" placeholder=\"seats_total\" style=\"width:130px\"> <input id=\"vh_cols\" placeholder=\"seat_columns (e.g. 2+2)\" style=\"width:150px\"> <button onclick=\"createVehicle()\">Create</button>
    </div>
    <div>
      <input id=\"vh_id\" size=\"36\" placeholder=\"vehicle_id\"> <input id=\"vh_name2\" placeholder=\"name\"> <input id=\"vh_seats2\" type=\"number\" placeholder=\"seats\" style=\"width:100px\"> <input id=\"vh_cols2\" placeholder=\"columns\" style=\"width:120px\"> <button onclick=\"updateVehicle()\">Update</button> <button onclick=\"deleteVehicle()\">Delete</button>
    </div>
    <pre id=\"vhout\"></pre>
  </div>
  <div class=\"card\">
    <h3>Promos</h3>
    <div>
      <button onclick=\"listPromos()\">List</button>
      <input id=\"pr_code\" placeholder=\"code\"> <input id=\"pr_bps\" type=\"number\" placeholder=\"percent_off_bps\" style=\"width:160px\"> <input id=\"pr_amt\" type=\"number\" placeholder=\"amount_off_cents\" style=\"width:160px\"> <label><input id=\"pr_active\" type=\"checkbox\"> active</label> <button onclick=\"createPromo()\">Create</button>
    </div>
    <div>
      <input id=\"pr_id\" size=\"36\" placeholder=\"promo_id\"> <input id=\"pr_bps2\" type=\"number\" placeholder=\"bps\" style=\"width:100px\"> <input id=\"pr_amt2\" type=\"number\" placeholder=\"amount\" style=\"width:120px\"> <label><input id=\"pr_act2\" type=\"checkbox\"> active</label> <button onclick=\"updatePromo()\">Update</button> <button onclick=\"deletePromo()\">Delete</button>
    </div>
    <pre id=\"prout\"></pre>
  </div>
</div>
<script nonce=\"{nonce}\">
const out=document.getElementById('out');
const opout=document.getElementById('opout');
const tkt=document.getElementById('tkt');
const brout=document.getElementById('brout');
const vhout=document.getElementById('vhout');
const prout=document.getElementById('prout');
function auth(){ const t=document.getElementById('tok').value.trim(); return t?{Authorization:'Bearer '+t}:{}};
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
function updateCSV(){
  const op = document.getElementById('opid').value.trim();
  if(!op){ return; }
  const st = document.getElementById('csv_status').value;
  let href = '/operators/' + encodeURIComponent(op) + '/bookings.csv';
  if (st) href += '?status=' + encodeURIComponent(st);
  const a = document.getElementById('csv');
  a.href = href;
  a.setAttribute('download','bookings.csv');
}
async function listTrips(){ const op=document.getElementById('opid').value.trim(); const r=await fetch('/operators/'+op+'/trips',{headers:auth()}); opout.textContent=await r.text(); }
async function summary(){ const op=document.getElementById('opid').value.trim(); const d=parseInt(document.getElementById('since').value||'7',10); const r=await fetch('/operators/'+op+'/reports/summary?since_days='+d,{headers:auth()}); opout.textContent=await r.text(); }
async function manifest(){ const op=document.getElementById('opid').value.trim(); const tid=document.getElementById('trip_id').value.trim(); const r=await fetch('/operators/'+op+'/trips/'+tid+'/manifest',{headers:auth()}); opout.textContent=await r.text(); }
async function validateQR(){ const op=document.getElementById('opid').value.trim(); const qr=document.getElementById('qr').value.trim(); const r=await fetch('/operators/'+op+'/tickets/validate?qr='+encodeURIComponent(qr),{headers:auth()}); tkt.textContent=await r.text(); }
async function board(){ const op=document.getElementById('opid').value.trim(); const bid=document.getElementById('bid').value.trim(); const r=await fetch('/operators/'+op+'/tickets/board?booking_id='+encodeURIComponent(bid),{method:'POST', headers:auth()}); tkt.textContent=await r.text(); }
async function cloneTrip(){ const op=document.getElementById('opid').value.trim(); const tid=document.getElementById('src_trip').value.trim(); const sd=document.getElementById('start').value.trim(); const ed=document.getElementById('end').value.trim(); const w=(document.getElementById('wds').value||'').split(',').map(x=>parseInt(x.trim(),10)).filter(n=>!isNaN(n)); const body={start_date: sd, end_date: ed, weekdays: w}; const r=await fetch('/operators/'+op+'/trips/'+tid+'/clone',{method:'POST', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); tkt.textContent=await r.text(); }
async function listBranches(){ const op=document.getElementById('opid').value.trim(); const r=await fetch('/operators/'+op+'/branches',{headers:auth()}); brout.textContent=await r.text(); }
async function createBranch(){ const op=document.getElementById('opid').value.trim(); const body={name: document.getElementById('br_name').value, commission_bps: parseInt(document.getElementById('br_fee').value||'0',10)}; const r=await fetch('/operators/'+op+'/branches',{method:'POST', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); brout.textContent=await r.text(); }
async function updateBranch(){ const op=document.getElementById('opid').value.trim(); const id=document.getElementById('br_id').value.trim(); const body={name: document.getElementById('br_name2').value, commission_bps: parseInt(document.getElementById('br_fee2').value||'0',10)}; const r=await fetch('/operators/'+op+'/branches/'+id,{method:'PATCH', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); brout.textContent=await r.text(); }
async function deleteBranch(){ const op=document.getElementById('opid').value.trim(); const id=document.getElementById('br_id').value.trim(); const r=await fetch('/operators/'+op+'/branches/'+id,{method:'DELETE', headers:auth()}); brout.textContent=await r.text(); }
async function listVehicles(){ const op=document.getElementById('opid').value.trim(); const r=await fetch('/operators/'+op+'/vehicles',{headers:auth()}); vhout.textContent=await r.text(); }
async function createVehicle(){ const op=document.getElementById('opid').value.trim(); const body={name: document.getElementById('vh_name').value, seats_total: parseInt(document.getElementById('vh_seats').value||'0',10), seat_columns: document.getElementById('vh_cols').value}; const r=await fetch('/operators/'+op+'/vehicles',{method:'POST', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); vhout.textContent=await r.text(); }
async function updateVehicle(){ const op=document.getElementById('opid').value.trim(); const id=document.getElementById('vh_id').value.trim(); const body={name: document.getElementById('vh_name2').value, seats_total: parseInt(document.getElementById('vh_seats2').value||'0',10), seat_columns: document.getElementById('vh_cols2').value}; const r=await fetch('/operators/'+op+'/vehicles/'+encodeURIComponent(id),{method:'PATCH', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); vhout.textContent=await r.text(); }
async function deleteVehicle(){ const op=document.getElementById('opid').value.trim(); const id=document.getElementById('vh_id').value.trim(); const r=await fetch('/operators/'+op+'/vehicles/'+id,{method:'DELETE', headers:auth()}); vhout.textContent=await r.text(); }
async function listPromos(){ const op=document.getElementById('opid').value.trim(); const r=await fetch('/operators/'+op+'/promos',{headers:auth()}); prout.textContent=await r.text(); }
async function createPromo(){ const op=document.getElementById('opid').value.trim(); const body={code: pr_code.value, percent_off_bps: pr_bps.value?parseInt(pr_bps.value,10):null, amount_off_cents: pr_amt.value?parseInt(pr_amt.value,10):null, valid_from:null, valid_until:null, max_uses:null, per_user_max_uses:null, min_total_cents:null, active: pr_active.checked}; const r=await fetch('/operators/'+op+'/promos',{method:'POST', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); prout.textContent=await r.text(); }
async function updatePromo(){ const op=document.getElementById('opid').value.trim(); const id=document.getElementById('pr_id').value.trim(); const body={percent_off_bps: pr_bps2.value?parseInt(pr_bps2.value,10):null, amount_off_cents: pr_amt2.value?parseInt(pr_amt2.value,10):null, active: document.getElementById('pr_act2').checked}; const r=await fetch('/operators/'+op+'/promos/'+id,{method:'PATCH', headers:{...auth(), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); prout.textContent=await r.text(); }
async function deletePromo(){ const op=document.getElementById('opid').value.trim(); const id=document.getElementById('pr_id').value.trim(); const r=await fetch('/operators/'+op+'/promos/'+id,{method:'DELETE', headers:auth()}); prout.textContent=await r.text(); }
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
