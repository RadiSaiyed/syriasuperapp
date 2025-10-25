from fastapi import FastAPI, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

# Import Livestock domain via PYTHONPATH=apps/livestock
from app.config import settings
from app.database import engine
from app.models import Base
from app.middleware_request_id import RequestIDMiddleware
from app.middleware_rate_limit import SlidingWindowLimiter, RedisRateLimiter
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
from app.routers import seller as seller_router
from app.auth import get_current_user
from app.database import get_db
from app.models import User, Ranch, AnimalListing, ProductListing, Order
from fastapi import HTTPException, status, Depends


def create_app() -> FastAPI:
    app = FastAPI(title="Livestock Seller API", version="0.1.0")

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
            {"name": "seller", "description": "Manage ranch, animals, products and orders"},
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
    app.include_router(seller_router.router)
    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Livestock Seller API", "version": "0.1.0", "env": settings.ENV}

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
    @app.get("/me", tags=["dashboard"])
    def me(user: User = Depends(get_current_user), db = Depends(get_db)):
        if user.role != "seller":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller only")
        ranch = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
        animals = db.query(AnimalListing).filter(AnimalListing.ranch_id == (ranch.id if ranch else None)).count() if ranch else 0
        products = db.query(ProductListing).filter(ProductListing.ranch_id == (ranch.id if ranch else None)).count() if ranch else 0
        orders = 0
        if ranch:
            animal_ids = [a.id for a in db.query(AnimalListing).filter(AnimalListing.ranch_id == ranch.id).all()]
            product_ids = [p.id for p in db.query(ProductListing).filter(ProductListing.ranch_id == ranch.id).all()]
            orders = db.query(Order).filter(((Order.type == "animal") & (Order.animal_id.in_(animal_ids))) | ((Order.type == "product") & (Order.product_id.in_(product_ids)))).count()
        from datetime import datetime, timedelta
        now = datetime.utcnow(); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        o7 = o30 = 0
        if ranch:
            o7 = db.query(Order).filter(((Order.type == "animal") & (Order.animal_id.in_(animal_ids))) | ((Order.type == "product") & (Order.product_id.in_(product_ids))), Order.created_at >= since7).count()
            o30 = db.query(Order).filter(((Order.type == "animal") & (Order.animal_id.in_(animal_ids))) | ((Order.type == "product") & (Order.product_id.in_(product_ids))), Order.created_at >= since30).count()
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name},
            "ranch": None if not ranch else {"id": str(ranch.id), "name": ranch.name},
            "animals_total": int(animals),
            "products_total": int(products),
            "orders_total": int(orders),
            "metrics": {"7d": {"orders_total": int(o7)}, "30d": {"orders_total": int(o30)}},
        }
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
    <h3>Ranch + Listings</h3>
    <div>
      <input id=\"rname\" placeholder=\"ranch name\"> <input id=\"rloc\" placeholder=\"location\"> <input id=\"rdesc\" placeholder=\"description\" size=\"32\">
      <button onclick=\"createRanch()\">Create Ranch</button>
      <button onclick=\"getRanch()\">Get Ranch</button>
    </div>
    <div>
      <h4>Animal</h4>
      <input id=\"aspecies\" placeholder=\"species\"> <input id=\"abreed\" placeholder=\"breed\"> <input id=\"asex\" placeholder=\"sex\" style=\"width:80px\"> <input id=\"aage\" type=\"number\" placeholder=\"age_months\" style=\"width:120px\"> <input id=\"aw\" type=\"number\" placeholder=\"weight_kg\" style=\"width:120px\"> <input id=\"ap\" type=\"number\" placeholder=\"price_cents\" style=\"width:140px\">
      <button onclick=\"createAnimal()\">Create</button>
      <button onclick=\"listAnimals()\">My Animals</button>
    </div>
    <div>
      <h4>Product</h4>
      <input id=\"ptype\" placeholder=\"product_type\"> <input id=\"unit\" placeholder=\"unit\"> <input id=\"pq\" type=\"number\" placeholder=\"quantity\" style=\"width:120px\"> <input id=\"pp\" type=\"number\" placeholder=\"price_per_unit_cents\" style=\"width:180px\">
      <button onclick=\"createProd()\">Create</button>
      <button onclick=\"listProds()\">My Products</button>
    </div>
    <div>
      <h4>Orders + Auctions</h4>
      <button onclick=\"listOrders()\">Orders</button>
      <input id=\"animal_id\" placeholder=\"animal_id\" size=\"36\"> <input id=\"sp\" type=\"number\" placeholder=\"starting_price_cents\"> <input id=\"ends\" placeholder=\"ends_at ISO\" size=\"24\"> <button onclick=\"createAuction()\">Create Auction</button>
    </div>
    <pre id=\"sout\"></pre>
  </div>
</div>
<script>
const out=document.getElementById('out');
const sout=document.getElementById('sout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function createRanch(){ const body={name:rname.value, location:rloc.value, description:rdesc.value}; const r=await fetch('/seller/ranch',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); sout.textContent=await r.text(); }
async function getRanch(){ const r=await fetch('/seller/ranch',{headers:auth()}); sout.textContent=await r.text(); }
async function createAnimal(){ const body={species:aspecies.value, breed:abreed.value, sex:asex.value, age_months:parseInt(aage.value||'0',10), weight_kg:parseInt(aw.value||'0',10), price_cents:parseInt(ap.value||'0',10)}; const r=await fetch('/seller/animals',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); sout.textContent=await r.text(); }
async function listAnimals(){ const r=await fetch('/seller/animals',{headers:auth()}); sout.textContent=await r.text(); }
async function createProd(){ const body={product_type:ptype.value, unit:unit.value, quantity:parseInt(pq.value||'0',10), price_per_unit_cents:parseInt(pp.value||'0',10)}; const r=await fetch('/seller/products',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); sout.textContent=await r.text(); }
async function listProds(){ const r=await fetch('/seller/products',{headers:auth()}); sout.textContent=await r.text(); }
async function listOrders(){ const r=await fetch('/seller/orders',{headers:auth()}); sout.textContent=await r.text(); }
async function createAuction(){ const body={animal_id:animal_id.value, starting_price_cents:parseInt(sp.value||'0',10), ends_at_iso:ends.value}; const r=await fetch('/seller/auctions',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); sout.textContent=await r.text(); }
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
