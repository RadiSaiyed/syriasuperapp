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
from app.routers import operator as operator_router
from app.auth import get_current_user
from app.database import get_db
from app.models import User, Restaurant, Order, OperatorMember
from fastapi import HTTPException, status, Depends


def create_app() -> FastAPI:
    app = FastAPI(title="Food Operator API", version="0.1.0")

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
        # Best-effort lightweight schema evolution for new columns
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS hours_json TEXT"
                )
                conn.exec_driver_sql(
                    "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS is_open_override BOOLEAN"
                )
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS special_hours_json TEXT")
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS busy_mode BOOLEAN DEFAULT FALSE")
                conn.exec_driver_sql("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS max_orders_per_hour INTEGER")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS preparing_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS out_for_delivery_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS last_status_at TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS kds_bumped BOOLEAN DEFAULT FALSE")
                conn.exec_driver_sql("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS packed BOOLEAN DEFAULT FALSE")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS visible BOOLEAN DEFAULT TRUE")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS category_id UUID")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS stock_qty INTEGER")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS oos_until TIMESTAMP NULL")
                conn.exec_driver_sql("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS station VARCHAR(32)")
                conn.exec_driver_sql("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS station_snapshot VARCHAR(32)")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS menu_categories (id UUID PRIMARY KEY, restaurant_id UUID NOT NULL REFERENCES restaurants(id), parent_id UUID NULL REFERENCES menu_categories(id), name VARCHAR(128) NOT NULL, description VARCHAR(512) NULL, sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL)")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS modifier_groups (id UUID PRIMARY KEY, restaurant_id UUID NOT NULL REFERENCES restaurants(id), name VARCHAR(128) NOT NULL, min_choices INTEGER NOT NULL DEFAULT 0, max_choices INTEGER NOT NULL DEFAULT 1, required BOOLEAN NOT NULL DEFAULT FALSE, sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL)")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS modifier_options (id UUID PRIMARY KEY, group_id UUID NOT NULL REFERENCES modifier_groups(id), name VARCHAR(128) NOT NULL, price_delta_cents INTEGER NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL)")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS menu_item_modifier_groups (id UUID PRIMARY KEY, menu_item_id UUID NOT NULL REFERENCES menu_items(id), group_id UUID NOT NULL REFERENCES modifier_groups(id), created_at TIMESTAMP NOT NULL, CONSTRAINT uq_menu_item_group UNIQUE (menu_item_id, group_id))")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS audit_logs (id UUID PRIMARY KEY, user_id UUID NULL REFERENCES users(id), action VARCHAR(64) NOT NULL, entity_type VARCHAR(64) NOT NULL, entity_id VARCHAR(64) NULL, before_json VARCHAR(4096) NULL, after_json VARCHAR(4096) NULL, created_at TIMESTAMP NOT NULL)")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS webhook_deliveries (id UUID PRIMARY KEY, endpoint_id UUID NULL REFERENCES food_webhook_endpoints(id), event VARCHAR(128) NOT NULL, payload_json VARCHAR(4096) NOT NULL, status VARCHAR(32) NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, last_error VARCHAR(512) NULL, created_at TIMESTAMP NOT NULL, updated_at TIMESTAMP NOT NULL)")
                conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS restaurant_stations (id UUID PRIMARY KEY, restaurant_id UUID NOT NULL REFERENCES restaurants(id), name VARCHAR(64) NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL)")
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
            {"name": "operator", "description": "Manage restaurants, orders and reports"},
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
    app.include_router(operator_router.router)

    @app.get("/me", tags=["dashboard"])
    def me(user: User = Depends(get_current_user), db = Depends(get_db)):
        mem = db.query(OperatorMember).filter(OperatorMember.user_id == user.id).one_or_none()
        if mem is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not operator member")
        rest_cnt = db.query(Restaurant).count()
        pending = db.query(Order).filter(Order.status.in_(["accepted", "preparing"])) .count()
        out_for_delivery = db.query(Order).filter(Order.status == "out_for_delivery").count()
        from datetime import datetime, timedelta
        now = datetime.utcnow(); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        orders7 = db.query(Order).filter(Order.created_at >= since7).count()
        orders30 = db.query(Order).filter(Order.created_at >= since30).count()
        delivered7 = db.query(Order).filter(Order.created_at >= since7, Order.status == "delivered").count()
        delivered30 = db.query(Order).filter(Order.created_at >= since30, Order.status == "delivered").count()
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name},
            "restaurants_total": int(rest_cnt),
            "orders_pending_preparing": int(pending),
            "orders_out_for_delivery": int(out_for_delivery),
            "metrics": {"7d": {"orders_total": int(orders7), "orders_delivered": int(delivered7)}, "30d": {"orders_total": int(orders30), "orders_delivered": int(delivered30)}},
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
        return {"service": "Food Operator API", "version": "0.1.0", "env": settings.ENV}
    
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
        # Minimal static UI scaffold that relies on a pasted JWT token for fetches
        html = """
<!doctype html>
<meta charset=\"utf-8\">
<title>Food Operator Portal</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;}
input,button{font-size:14px;padding:6px 8px;margin:4px}
pre{background:#f6f8fa;padding:12px;border-radius:6px;}
.row{margin:8px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{border:1px solid #e5e7eb;border-radius:8px;padding:12px}
.small{font-size:12px;color:#6b7280}
</style>
<h1>Food Operator Portal</h1>
<div class=\"row\">
  <label>Bearer Token:</label>
  <input id=\"tok\" size=\"60\" placeholder=\"paste JWT...\">
  <button onclick=\"load()\">Load</button>
  <button onclick=\"clearOut()\">Clear</button>
  <div id=\"msg\"></div>
  <div class=\"row\"><small>Tip: Use /auth endpoints to obtain a token.</small></div>
  <div class=\"row\"><a href=\"/docs\">OpenAPI Docs</a></div>
</div>
  <div class=\"grid\">
  <div class=\"card\">
  <div class="card">
    <h3>Restaurant Admin</h3>
    <div class="small">Create Restaurant</div>
    <div class="row">
      <input id="r_name" placeholder="name"> <input id="r_city" placeholder="city"> <input id="r_addr" placeholder="address" size="28"> <input id="r_owner" placeholder="owner_phone"> <button onclick="createRestaurant()">Create</button>
    </div>
    <div class="small">Hours</div>
    <div class="row">
      <input id="hrs_rid" size="36" placeholder="restaurant_id"> <button onclick="getHours()">Get</button>
    </div>
    <div class="row">
      <textarea id="hrs_json" rows="3" style="width:100%" placeholder="{\n  &quot;mon&quot;: [[&quot;09:00&quot;,&quot;17:00&quot;]]\n}"></textarea>
      <input id="hrs_special" size="36" placeholder="special_hours_json (opt)"> <label><input id="hrs_open" type="checkbox"> open override</label> <button onclick="setHours()">Set</button>
    </div>
    <div class="small">Menu Item</div>
    <div class="row">
      <input id="mi_rid" size="36" placeholder="restaurant_id"> <input id="mi_name" placeholder="name"> <input id="mi_price" type="number" placeholder="price_cents" style="width:140px"> <input id="mi_desc" placeholder="description" size="24"> <label><input id="mi_av" type="checkbox" checked> available</label> <button onclick="createMenuItem()">Create</button>
    </div>
    <div class="small">Images</div>
    <div class="row">
      <input id="img_rid" size="36" placeholder="restaurant_id"> <input id="img_url" placeholder="image URL" size="28"> <input id="img_sort" type="number" placeholder="sort_order" style="width:140px"> <button onclick="addRImage()">Add</button> <button onclick="listRImages()">List</button>
    </div>
    <pre id="admin_out"></pre>
  </div>

    <h3>Quick</h3>
    <div class=\"row\">
      <input id=\"days\" type=\"number\" value=\"7\" style=\"width:80px\" oninput=\"onDays()\"/> days
      <button onclick=\"me()\">/me</button>
      <button onclick=\"listRestaurants()\">/operator/restaurants</button>
      <button onclick=\"summary()\">summary</button>
      <button onclick=\"sla()\">sla</button>
      <a id=\"payout_xlsx\" href=\"/operator/reports/payout.xlsx?days=7\" target=\"_blank\">payout.xlsx</a>
      <a id=\"payout_pdf\" href=\"/operator/reports/payout.pdf?days=7\" target=\"_blank\">payout.pdf</a>
      <button id=\"retry_hooks\" onclick=\"retryHooks()\">Retry Webhooks</button>
    </div>
    <pre id=\"out\"></pre>
  </div>
  <div class=\"card\">
    <h3>Categories</h3>
    <div class=\"small\">Restaurant ID:</div>
    <input id=\"rid\" size=\"40\" placeholder=\"restaurant UUID\">
    <div class=\"row\">
      <button onclick=\"listCats()\">List</button>
    </div>
    <div class=\"row\" id=\"createCatRow\">
      <input id=\"cat_name\" placeholder=\"name\"> <input id=\"cat_parent\" placeholder=\"parent_id (opt)\"> <input id=\"cat_sort\" type=\"number\" placeholder=\"sort\" value=\"0\">
      <button onclick=\"createCat()\">Create</button>
    </div>
    <pre id=\"cats\"></pre>
  </div>
  <div class=\"card\">
    <h3>Modifiers</h3>
    <div class=\"small\">Restaurant ID:</div>
    <input id=\"gid_rest\" size=\"40\" placeholder=\"restaurant UUID\">
    <div class=\"row\">
      <button onclick=\"listGroups()\">List Groups</button>
    </div>
    <div class=\"row\" id=\"createGrpRow\">
      <input id=\"grp_name\" placeholder=\"name\"> <input id=\"grp_min\" type=\"number\" value=\"0\"> <input id=\"grp_max\" type=\"number\" value=\"1\"> <label><input id=\"grp_req\" type=\"checkbox\"> required</label>
      <button onclick=\"createGroup()\">Create</button>
    </div>
    <div class=\"row\" id=\"createOptRow\">
      <input id=\"opt_gid\" placeholder=\"group_id\"> <input id=\"opt_name\" placeholder=\"option name\"> <input id=\"opt_price\" type=\"number\" value=\"0\">
      <button onclick=\"createOption()\">Add Option</button>
    </div>
    <pre id=\"mods\"></pre>
  </div>
  <div class=\"card\">
    <h3>Items</h3>
    <div class=\"small\">Restaurant ID:</div>
    <input id=\"items_rid\" size=\"40\" placeholder=\"restaurant UUID\">
    <div class=\"row\">
      <button onclick=\"listItems()\">List Items</button>
      <button onclick=\"downloadItemsCSV()\">Download Items CSV</button>
      <button onclick=\"downloadItemsXLSX()\">Download Items XLSX</button>
    </div>
    <div id=\"items_list\" class=\"small\"></div>
    <div class=\"row\" id=\"items_st_create_row\">
      <input id=\"items_st_name\" placeholder=\"station name\"> <input id=\"items_st_sort\" type=\"number\" value=\"0\" style=\"width:80px\">
      <button onclick=\"createItemStation()\">Create Station</button>
    </div>
    <div id=\"items_stations\" class=\"small\"></div>
  </div>
  <div class=\"card\">
    <h3>Stations</h3>
    <div class=\"small\">Restaurant ID:</div>
    <input id=\"st_rid\" size=\"40\" placeholder=\"restaurant UUID\">
    <div class=\"row\">
      <button onclick=\"listStations()\">List</button>
    </div>
    <div class=\"row\" id=\"st_create_row\">
      <input id=\"st_name\" placeholder=\"name\"> <input id=\"st_sort\" type=\"number\" value=\"0\" style=\"width:80px\">
      <button onclick=\"createStation()\">Create</button>
    </div>
    <pre id=\"st_out\"></pre>
  </div>
  <div class=\"card\">
    <h3>Bulk Stock (CSV)</h3>
    <div class=\"small\">Restaurant ID:</div>
    <input id=\"csv_rid\" size=\"40\" placeholder=\"restaurant UUID\">
    <div class=\"small\">CSV columns: id|name,stock_qty,available,visible,oos_until,station</div>
    <div class=\"row\">
      <button onclick=\"downloadTemplate()\">Download XLSX Template</button>
      <input type=\"file\" id=\"csv_file\" accept=\".xlsx\">
      <button onclick=\"uploadXLSX()\">Upload XLSX</button>
    </div>
    <textarea id=\"csv_text\" rows=\"6\" style=\"width:100%\" placeholder=\"id,stock_qty,available\n...\"></textarea>
    <div class=\"row\"><button onclick=\"uploadCSV()\">Apply</button> <a id=\"csv_dl\" href=\"#\" download=\"bulk_report.json\" style=\"display:none\">Download Report</a></div>
    <pre id=\"csv_out\"></pre>
  </div>
  <div class=\"card\">
    <h3>Items</h3>
    <div class=\"small\">Restaurant ID:</div>
    <input id=\"items_rid\" size=\"40\" placeholder=\"restaurant UUID\">
    <div class=\"row\">
      <button onclick=\"listItems()\">List Items</button>
    </div>
    <div id=\"items_list\" class=\"small\"></div>
  </div>
  <div class=\"card\" id=\"bulkCard\">
    <h3>Bulk Orders</h3>
    <div class=\"small\">Order IDs (comma-separated UUIDs):</div>
    <input id=\"oids\" size=\"60\" placeholder=\"id1,id2,...\">
    <select id=\"ost\"><option>accepted</option><option>preparing</option><option>out_for_delivery</option><option>delivered</option></select>
    <button onclick=\"bulkStatus()\">Apply</button>
    <pre id=\"bulk\"></pre>
  </div>
  <div class=\"card\">
    <h3>KDS</h3>
    <div class=\"row\">
      <select id=\"kds_status\"><option>accepted</option><option>preparing</option></select>
      <button onclick=\"listKDS()\">List</button>
    </div>
    <div class=\"row\">
      <input id=\"kds_oid\" size=\"40\" placeholder=\"order UUID\"> 
      <select id=\"kds_to\"><option>preparing</option><option>out_for_delivery</option><option>delivered</option></select>
      <button onclick=\"bumpKDS()\">Bump</button>
    </div>
    <pre id=\"kds_out\"></pre>
  </div>
  <div class=\"card\">
    <h3>Stock</h3>
    <div class=\"small\">Menu Item ID:</div>
    <input id=\"stock_mid\" size=\"40\" placeholder=\"menu_item UUID\">
    <div class=\"row\">
      <input id=\"stock_qty\" type=\"number\" placeholder=\"qty\"> <label><input id=\"stock_av\" type=\"checkbox\"> available</label>
      <button onclick=\"updateStock()\">Update</button>
    </div>
    <pre id=\"stock_out\"></pre>
  </div>
</div>
<script>
let ROLE='';
let CURRENT_STATIONS=[];
let CURRENT_ITEMS=[];
function clearOut(){document.getElementById('out').textContent='';}
function getDays(){const v=parseInt(document.getElementById('days').value||'7',10);return isNaN(v)?7:Math.max(1,Math.min(180,v));}
function setRole(r){ROLE=r||''; const isMgr=(ROLE==='admin'||ROLE==='manager');
  for(const id of ['createCatRow','createGrpRow','createOptRow','bulkCard']){const el=document.getElementById(id); if(el){el.style.display=isMgr?'block':'none';}}
  const payout=document.getElementById('payout_xlsx'); if(payout){payout.style.display=isMgr?'inline':'none';}
  const retry=document.getElementById('retry_hooks'); if(retry){retry.style.display=isMgr?'inline':'none';}
}
async function api(path){
  const t=document.getElementById('tok').value.trim();
  if(!t){document.getElementById('msg').textContent='Paste a token first';return}
  const r=await fetch(path,{headers:{'Authorization':'Bearer '+t}});
  const ct=r.headers.get('content-type')||'';
  const txt=ct.includes('application/json')? JSON.stringify(await r.json(),null,2): await r.text();
  document.getElementById('out').textContent = '$ '+path+'\n\n'+txt;
}
function updatePayoutHref(){const d=getDays(); const a=document.getElementById('payout_xlsx'); if(a){a.href='/operator/reports/payout.xlsx?days='+d;}}
async function me(){const t=document.getElementById('tok').value.trim(); const r=await fetch('/me',{headers:{'Authorization':'Bearer '+t}}); const j=await r.json(); setRole(((j||{}).user||{}).role||''); document.getElementById('out').textContent=JSON.stringify(j,null,2);}
function load(){document.getElementById('msg').textContent='Token set'; me(); updatePayoutHref();}
function onDays(){updatePayoutHref();}
async function listRestaurants(){api('/operator/restaurants');}
async function summary(){const d=getDays(); api('/operator/reports/summary?days='+d);}
async function sla(){const d=getDays(); api('/operator/reports/sla?days='+d);}
async function retryHooks(){const t=document.getElementById('tok').value.trim(); const r=await fetch('/operator/webhooks/retry',{method:'POST',headers:{'Authorization':'Bearer '+t}}); document.getElementById('out').textContent=await r.text();}
async function listKDS(){
  const t=document.getElementById('tok').value.trim(); const st=document.getElementById('kds_status').value; 
  const r=await fetch('/operator/kds/orders?status='+encodeURIComponent(st),{headers:{'Authorization':'Bearer '+t}});
  document.getElementById('kds_out').textContent=JSON.stringify(await r.json(),null,2);
}
async function bumpKDS(){
  const t=document.getElementById('tok').value.trim(); const id=document.getElementById('kds_oid').value.trim(); const to=document.getElementById('kds_to').value;
  const r=await fetch('/operator/kds/orders/'+id+'/bump?to_status='+encodeURIComponent(to),{method:'POST',headers:{'Authorization':'Bearer '+t}});
  document.getElementById('kds_out').textContent=await r.text();
}
async function listCats(){
  const rid=document.getElementById('rid').value.trim();
  if(!rid) return;
  const t=document.getElementById('tok').value.trim();
  const r=await fetch('/operator/restaurants/'+rid+'/categories',{headers:{'Authorization':'Bearer '+t}});
  document.getElementById('cats').textContent=JSON.stringify(await r.json(),null,2);
}
async function createCat(){
  const rid=document.getElementById('rid').value.trim();
  const t=document.getElementById('tok').value.trim();
  const name=document.getElementById('cat_name').value.trim();
  const parent=document.getElementById('cat_parent').value.trim();
  const sort=parseInt(document.getElementById('cat_sort').value||'0',10);
  const body={name:name, parent_id: parent||null, sort_order: sort};
  const r=await fetch('/operator/restaurants/'+rid+'/categories',{method:'POST', headers:{'Authorization':'Bearer '+t,'Content-Type':'application/json'}, body: JSON.stringify(body)});
  document.getElementById('cats').textContent=await r.text();
}
async function listGroups(){
  const rid=document.getElementById('gid_rest').value.trim();
  if(!rid) return;
  const t=document.getElementById('tok').value.trim();
  const r=await fetch('/operator/restaurants/'+rid+'/modifier_groups',{headers:{'Authorization':'Bearer '+t}});
  document.getElementById('mods').textContent=JSON.stringify(await r.json(),null,2);
}
async function createGroup(){
  const rid=document.getElementById('gid_rest').value.trim();
  const t=document.getElementById('tok').value.trim();
  const name=document.getElementById('grp_name').value.trim();
  const min=parseInt(document.getElementById('grp_min').value||'0',10);
  const max=parseInt(document.getElementById('grp_max').value||'1',10);
  const req=document.getElementById('grp_req').checked;
  const body={name:name, min_choices:min, max_choices:max, required:req};
  const r=await fetch('/operator/restaurants/'+rid+'/modifier_groups',{method:'POST', headers:{'Authorization':'Bearer '+t,'Content-Type':'application/json'}, body: JSON.stringify(body)});
  document.getElementById('mods').textContent=await r.text();
}
async function createOption(){
  const gid=document.getElementById('opt_gid').value.trim();
  const t=document.getElementById('tok').value.trim();
  const name=document.getElementById('opt_name').value.trim();
  const price=parseInt(document.getElementById('opt_price').value||'0',10);
  const body={name:name, price_delta_cents:price};
  const r=await fetch('/operator/modifier_groups/'+gid+'/options',{method:'POST', headers:{'Authorization':'Bearer '+t,'Content-Type':'application/json'}, body: JSON.stringify(body)});
  document.getElementById('mods').textContent=await r.text();
}
async function listItems(){
  const rid=document.getElementById('items_rid').value.trim();
  const t=document.getElementById('tok').value.trim();
  if(!rid||!t){return}
  try{
    const rs=await fetch('/operator/restaurants/'+rid+'/stations',{headers:{'Authorization':'Bearer '+t}});
    CURRENT_STATIONS = await rs.json();
  }catch(e){ CURRENT_STATIONS=[] }
  const r=await fetch('/operator/restaurants/'+rid+'/menu',{headers:{'Authorization':'Bearer '+t}});
  const j=await r.json();
  renderItems(j||[]);
}
function renderItems(arr){
  const el=document.getElementById('items_list');
  const isMgr=(ROLE==='admin'||ROLE==='manager');
  if(!Array.isArray(arr)){ el.textContent='No items'; return }
  let html='<table><tr><th>Name</th><th>Price</th><th>Avail</th><th>Visible</th><th>Stock</th><th>OOS until</th><th>Station</th><th>Actions</th></tr>';
  for(const it of arr){
    const av = (it.available===false)?'false':'true';
    const vis = (it.visible===false)?'false':'true';
    const stock = (it.stock_qty==null?'-':it.stock_qty);
    const oos = it.oos_until? new Date(it.oos_until).toISOString().slice(0,16) : '';
    html+=`<tr><td>${it.name}</td><td>${it.price_cents}</td><td>${av}</td><td>${vis}</td>`;
    if(isMgr){
      html+=`<td><input type=number id="stk_${it.id}" value="${stock==='-'?0:stock}" style="width:70px"></td>`;
      html+=`<td><input type="datetime-local" id="oos_${it.id}" value="${oos}"></td>`;
      let opts = '<option value="">-</option>';
      try{
        for(const s of (CURRENT_STATIONS||[])){
          const sel = (s.name===it.station)?' selected':'';
          opts += `<option value="${s.name}"${sel}>${s.name}</option>`;
        }
      }catch(e){}
      html+=`<td><select id="st_${it.id}">${opts}</select></td>`;
    } else {
      html+=`<td>${stock}</td><td>${oos||'-'}</td><td>-</td>`;
    }
    html+=`<td>`;
    if(isMgr){
      html+=`<button onclick=\"toggleAvail('${it.id}',${av==='true'?'false':'true'})\">${av==='true'?'disable':'enable'}</button>`;
      html+=` <button onclick=\"toggleVisible('${it.id}',${vis==='true'?'false':'true'})\">${vis==='true'?'hide':'show'}</button>`;
      html+=` <button onclick=\"saveStock('${it.id}')\">save stock</button>`;
      html+=` <button onclick=\"saveOOS('${it.id}')\">save oos</button>`;
      html+=` <button onclick=\"saveStation('${it.id}')\">save station</button>`;
    }
    html+='</td></tr>'
  }
  html+='</table>';
  el.innerHTML=html;
  // render inline stations list for this restaurant
  renderItemsStations();
}
function downloadItemsCSV(){
  try{
    const rows = CURRENT_ITEMS||[];
    let csv = 'id,name,price_cents,available,visible,stock_qty,oos_until,station\n';
    for(const it of rows){
      const vals=[it.id, it.name, it.price_cents, (it.available!==false), (it.visible!==false), (it.stock_qty==null?'':it.stock_qty), (it.oos_until||''), (it.station||'')];
      csv += vals.map(v=>String(v).replaceAll('"','""')).map(s=>`"${s}"`).join(',') + '\n';
    }
    const a = document.createElement('a'); a.download='items.csv'; a.href='data:text/csv;base64,'+btoa(unescape(encodeURIComponent(csv))); a.click();
  }catch(e){ console.error(e); }
}
async function saveStock(id){
  const t=document.getElementById('tok').value.trim(); const qty=document.getElementById('stk_'+id).value;
  await fetch('/operator/menu/'+id+'?stock_qty='+encodeURIComponent(qty),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function saveOOS(id){
  const t=document.getElementById('tok').value.trim(); let v=document.getElementById('oos_'+id).value;
  if(v){ try{ v = new Date(v).toISOString(); }catch(e){} }
  await fetch('/operator/menu/'+id+'?oos_until='+encodeURIComponent(v),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function saveStation(id){
  const t=document.getElementById('tok').value.trim(); const st=document.getElementById('st_'+id).value;
  await fetch('/operator/menu/'+id+'?station='+encodeURIComponent(st),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function listStations(){
  const rid=document.getElementById('st_rid').value.trim();
  const t=document.getElementById('tok').value.trim(); if(!rid||!t){return}
  const r=await fetch('/operator/restaurants/'+rid+'/stations',{headers:{'Authorization':'Bearer '+t}});
  const arr = await r.json();
  let html='<table><tr><th>Name</th><th>Sort</th><th>Actions</th></tr>';
  for(const s of (arr||[])){
    html+=`<tr><td>${s.name}</td><td>${s.sort_order}</td><td><button onclick=\"deleteStation('${s.id}')\">Delete</button></td></tr>`;
  }
  html+='</table>';
  document.getElementById('st_out').innerHTML=html;
}
async function createStation(){
  const rid=document.getElementById('st_rid').value.trim();
  const t=document.getElementById('tok').value.trim(); const name=document.getElementById('st_name').value.trim(); const sort=document.getElementById('st_sort').value||'0';
  if(!name) return;
  const r=await fetch('/operator/restaurants/'+rid+'/stations?name='+encodeURIComponent(name)+'&sort_order='+encodeURIComponent(sort),{method:'POST', headers:{'Authorization':'Bearer '+t}});
  document.getElementById('st_out').textContent=await r.text();
  await listStations();
  if(document.getElementById('items_rid').value.trim()===rid){ listItems(); }
}
async function renderItemsStations(){
  const rid=document.getElementById('items_rid').value.trim(); if(!rid) return;
  const t=document.getElementById('tok').value.trim(); if(!t) return;
  try{
    const rs=await fetch('/operator/restaurants/'+rid+'/stations',{headers:{'Authorization':'Bearer '+t}});
    const arr = await rs.json();
    let html='<table><tr><th>Name</th><th>Sort</th><th>Actions</th></tr>';
    for(const s of (arr||[])){
      html+=`<tr><td>${s.name}</td><td>${s.sort_order}</td><td><button onclick=\"deleteItemStation('${s.id}')\">Delete</button></td></tr>`;
    }
    html+='</table>';
    document.getElementById('items_stations').innerHTML=html;
    CURRENT_STATIONS = arr;
  }catch(e){ document.getElementById('items_stations').textContent=''; }
}
async function createItemStation(){
  const rid=document.getElementById('items_rid').value.trim(); const t=document.getElementById('tok').value.trim();
  const name=document.getElementById('items_st_name').value.trim(); const sort=document.getElementById('items_st_sort').value||'0';
  if(!name) return;
  await fetch('/operator/restaurants/'+rid+'/stations?name='+encodeURIComponent(name)+'&sort_order='+encodeURIComponent(sort),{method:'POST', headers:{'Authorization':'Bearer '+t}});
  await renderItemsStations();
  listItems();
}
async function deleteItemStation(id){
  const t=document.getElementById('tok').value.trim();
  await fetch('/operator/stations/'+id,{method:'DELETE', headers:{'Authorization':'Bearer '+t}});
  await renderItemsStations();
  listItems();
}
function downloadItemsXLSX(){
  const rid=document.getElementById('items_rid').value.trim(); if(!rid) return;
  window.open('/operator/restaurants/'+rid+'/items.xlsx','_blank');
}
async function deleteStation(id){
  const t=document.getElementById('tok').value.trim();
  await fetch('/operator/stations/'+id,{method:'DELETE', headers:{'Authorization':'Bearer '+t}});
  await listStations();
  const rid=document.getElementById('st_rid').value.trim();
  if(document.getElementById('items_rid').value.trim()===rid){ listItems(); }
}
async function uploadCSV(){
  const rid=document.getElementById('csv_rid').value.trim();
  const t=document.getElementById('tok').value.trim(); const txt=document.getElementById('csv_text').value;
  const r=await fetch('/operator/restaurants/'+rid+'/bulk_stock',{method:'POST', headers:{'Authorization':'Bearer '+t,'Content-Type':'text/csv'}, body: txt});
  const txtOut = await r.text();
  document.getElementById('csv_out').textContent=txtOut;
  try{
    const a=document.getElementById('csv_dl'); const b64=btoa(unescape(encodeURIComponent(txtOut)));
    a.href='data:application/json;base64,'+b64; a.style.display='inline';
  }catch(e){}
  // Also provide CSV variant from server for convenience
  try{
    const rc=await fetch('/operator/restaurants/'+rid+'/bulk_stock?format=csv',{method:'POST', headers:{'Authorization':'Bearer '+t,'Content-Type':'text/csv'}, body: txt});
    const csvTxt = await rc.text();
    const link = document.getElementById('csv_dl_csv') || (function(){const l=document.createElement('a'); l.id='csv_dl_csv'; l.textContent='Download Report (CSV)'; l.download='bulk_report.csv'; document.getElementById('csv_out').parentElement.insertBefore(l, document.getElementById('csv_out')); return l;})();
    link.href='data:text/csv;base64,'+btoa(unescape(encodeURIComponent(csvTxt)));
    link.style.display='inline';
  }catch(e){}
}
function downloadTemplate(){
  const rid=document.getElementById('csv_rid').value.trim(); if(!rid) return;
  window.open('/operator/restaurants/'+rid+'/bulk_stock_template.xlsx','_blank');
}
async function uploadXLSX(){
  const rid=document.getElementById('csv_rid').value.trim(); const t=document.getElementById('tok').value.trim();
  const f=document.getElementById('csv_file').files[0]; if(!f){return}
  const fd=new FormData(); fd.append('file', f);
  const r=await fetch('/operator/restaurants/'+rid+'/bulk_stock.xlsx',{method:'POST', headers:{'Authorization':'Bearer '+t}, body: f});
  const txtOut = await r.text();
  document.getElementById('csv_out').textContent=txtOut;
  try{
    const a=document.getElementById('csv_dl'); const b64=btoa(unescape(encodeURIComponent(txtOut)));
    a.href='data:application/json;base64,'+b64; a.style.display='inline';
  }catch(e){}
  try{
    const rc=await fetch('/operator/restaurants/'+rid+'/bulk_stock.xlsx?format=csv',{method:'POST', headers:{'Authorization':'Bearer '+t}, body: f});
    const csvTxt = await rc.text();
    const link = document.getElementById('csv_dl_csv') || (function(){const l=document.createElement('a'); l.id='csv_dl_csv'; l.textContent='Download Report (CSV)'; l.download='bulk_report.csv'; document.getElementById('csv_out').parentElement.insertBefore(l, document.getElementById('csv_out')); return l;})();
    link.href='data:text/csv;base64,'+btoa(unescape(encodeURIComponent(csvTxt)));
    link.style.display='inline';
  }catch(e){}
}
async function listItems(){
  const rid=document.getElementById('items_rid').value.trim();
  const t=document.getElementById('tok').value.trim();
  if(!rid||!t){return}
  const r=await fetch('/operator/restaurants/'+rid+'/menu',{headers:{'Authorization':'Bearer '+t}});
  const j=await r.json();
  renderItems(j||[]);
}
function renderItems(arr){
  const el=document.getElementById('items_list');
  const isMgr=(ROLE==='admin'||ROLE==='manager');
  if(!Array.isArray(arr)){ el.textContent='No items'; return }
  let html='<table><tr><th>Name</th><th>Price</th><th>Avail</th><th>Visible</th><th>Stock</th><th>OOS until</th><th>Station</th><th>Actions</th></tr>';
  for(const it of arr){
    const av = (it.available===false)?'false':'true';
    const vis = (it.visible===false)?'false':'true';
    const stock = (it.stock_qty==null?'-':it.stock_qty);
    const oos = it.oos_until? new Date(it.oos_until).toISOString().slice(0,16) : '';
    html+=`<tr><td>${it.name}</td><td>${it.price_cents}</td><td>${av}</td><td>${vis}</td>`;
    if(isMgr){
      html+=`<td><input type=number id="stk_${it.id}" value="${stock==='-'?0:stock}" style="width:70px"></td>`;
      html+=`<td><input type="datetime-local" id="oos_${it.id}" value="${oos}"></td>`;
      let opts = '<option value="">-</option>';
      try{
        for(const s of (CURRENT_STATIONS||[])){
          const sel = (s.name===it.station)?' selected':'';
          opts += `<option value="${s.name}"${sel}>${s.name}</option>`;
        }
      }catch(e){}
      html+=`<td><select id="st_${it.id}">${opts}</select></td>`;
    } else {
      html+=`<td>${stock}</td><td>${oos||'-'}</td><td>-</td>`;
    }
    html+=`<td>`;
    if(isMgr){
      html+=`<button onclick=\"toggleAvail('${it.id}',${av==='true'?'false':'true'})\">${av==='true'?'disable':'enable'}</button>`;
      html+=` <button onclick=\"toggleVisible('${it.id}',${vis==='true'?'false':'true'})\">${vis==='true'?'hide':'show'}</button>`;
      html+=` <button onclick=\"saveStock('${it.id}')\">save stock</button>`;
      html+=` <button onclick=\"saveOOS('${it.id}')\">save oos</button>`;
      html+=` <button onclick=\"saveStation('${it.id}')\">save station</button>`;
    }
    html+='</td></tr>'
  }
  html+='</table>';
  el.innerHTML=html;
}
async function saveStock(id){
  const t=document.getElementById('tok').value.trim(); const qty=document.getElementById('stk_'+id).value;
  await fetch('/operator/menu/'+id+'?stock_qty='+encodeURIComponent(qty),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function saveOOS(id){
  const t=document.getElementById('tok').value.trim(); let v=document.getElementById('oos_'+id).value;
  if(v){
    try{ v = new Date(v).toISOString(); }catch(e){}
  }
  await fetch('/operator/menu/'+id+'?oos_until='+encodeURIComponent(v),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function saveStation(id){
  const t=document.getElementById('tok').value.trim(); const st=document.getElementById('st_'+id).value;
  await fetch('/operator/menu/'+id+'?station='+encodeURIComponent(st),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function listItems(){
  const rid=document.getElementById('items_rid').value.trim();
  const t=document.getElementById('tok').value.trim();
  if(!rid||!t){return}
  const r=await fetch('/operator/restaurants/'+rid+'/menu',{headers:{'Authorization':'Bearer '+t}});
  const j=await r.json();
  renderItems(j||[]);
}
function renderItems(arr){
  const el=document.getElementById('items_list');
  const isMgr=(ROLE==='admin'||ROLE==='manager');
  if(!Array.isArray(arr)){ el.textContent='No items'; return }
  let html='<table><tr><th>Name</th><th>Price</th><th>Avail</th><th>Visible</th><th>Stock</th><th>Actions</th></tr>';
  for(const it of arr){
    const av = (it.available===false)?'false':'true';
    const vis = (it.visible===false)?'false':'true';
    const stock = (it.stock_qty==null?'-':it.stock_qty);
    html+=`<tr><td>${it.name}</td><td>${it.price_cents}</td><td>${av}</td><td>${vis}</td><td>${stock}</td><td>`;
    if(isMgr){
      html+=`<button onclick=\"toggleAvail('${it.id}',${av==='true'?'false':'true'})\">${av==='true'?'disable':'enable'}</button>`;
      html+=` <button onclick=\"toggleVisible('${it.id}',${vis==='true'?'false':'true'})\">${vis==='true'?'hide':'show'}</button>`;
    }
    html+='</td></tr>'
  }
  html+='</table>';
  el.innerHTML=html;
}
async function toggleAvail(id, v){
  const t=document.getElementById('tok').value.trim();
  await fetch('/operator/menu/'+id+'?available='+(v?'true':'false'),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function toggleVisible(id, v){
  const t=document.getElementById('tok').value.trim();
  await fetch('/operator/menu/'+id+'?visible='+(v?'true':'false'),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  listItems();
}
async function bulkStatus(){
  const t=document.getElementById('tok').value.trim();
  const ids=(document.getElementById('oids').value||'').split(',').map(x=>x.trim()).filter(Boolean);
  const st=document.getElementById('ost').value;
  const qs=ids.map(id=>'order_ids='+encodeURIComponent(id)).join('&');
  const r=await fetch('/operator/orders/bulk_status?'+qs+'&status_value='+encodeURIComponent(st),{method:'POST', headers:{'Authorization':'Bearer '+t}});
  document.getElementById('bulk').textContent=await r.text();
}
async function updateStock(){
  const t=document.getElementById('tok').value.trim();
  const id=document.getElementById('stock_mid').value.trim();
  const qty=document.getElementById('stock_qty').value;
  const av=document.getElementById('stock_av').checked;
  const qs=['stock_qty='+encodeURIComponent(qty)]; if(av) qs.push('available=true');
  const r=await fetch('/operator/menu/'+id+'?'+qs.join('&'),{method:'PATCH', headers:{'Authorization':'Bearer '+t}});
  document.getElementById('stock_out').textContent=await r.text();
}

async function createRestaurant(){ const body=new URLSearchParams(); body.append('name', r_name.value); if(r_city.value) body.append('city', r_city.value); if(r_addr.value) body.append('address', r_addr.value); if(r_owner.value) body.append('owner_phone', r_owner.value); const r=await fetch('/operator/restaurants',{method:'POST', headers: {'Authorization': 'Bearer '+(document.getElementById('tok').value||'')}, body}); admin_out.textContent=await r.text(); }
async function getHours(){ const id=document.getElementById('hrs_rid').value.trim(); const r=await fetch('/operator/restaurants/'+id+'/hours',{headers: {'Authorization': 'Bearer '+(document.getElementById('tok').value||'')}}); admin_out.textContent=await r.text(); }
async function setHours(){ const id=document.getElementById('hrs_rid').value.trim(); try{ JSON.parse(document.getElementById('hrs_json').value||'{}'); }catch(e){ alert('Invalid hours_json'); return;} const params=new URLSearchParams(); const body={'hours': JSON.parse(document.getElementById('hrs_json').value||'{}')}; let qs=''; const sp=document.getElementById('hrs_special').value.trim(); if(sp) qs += (qs?'&':'?')+'special_hours_json='+encodeURIComponent(sp); if(document.getElementById('hrs_open').checked) qs += (qs?'&':'?')+'is_open_override=true'; const r=await fetch('/operator/restaurants/'+id+'/hours'+qs,{method:'POST', headers:{'Authorization': 'Bearer '+(document.getElementById('tok').value||''), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); admin_out.textContent=await r.text(); }
async function createMenuItem(){ const rid=document.getElementById('mi_rid').value.trim(); const params=new URLSearchParams(); params.append('name', mi_name.value); params.append('price_cents', String(parseInt(mi_price.value||'0',10))); if(mi_desc.value) params.append('description', mi_desc.value); if(document.getElementById('mi_av').checked) params.append('available','true'); const r=await fetch('/operator/restaurants/'+rid+'/menu',{method:'POST', headers:{'Authorization': 'Bearer '+(document.getElementById('tok').value||'')}, body: params}); admin_out.textContent=await r.text(); }
async function addRImage(){ const rid=document.getElementById('img_rid').value.trim(); const body=[{url: img_url.value, sort_order: parseInt(img_sort.value||'0',10)}]; const r=await fetch('/operator/restaurants/'+rid+'/images',{method:'POST', headers:{'Authorization': 'Bearer '+(document.getElementById('tok').value||''), 'Content-Type':'application/json'}, body: JSON.stringify(body)}); admin_out.textContent=await r.text(); }
async function listRImages(){ const rid=document.getElementById('img_rid').value.trim(); const r=await fetch('/operator/restaurants/'+rid+'/images',{headers:{'Authorization': 'Bearer '+(document.getElementById('tok').value||'')}}); admin_out.textContent=await r.text(); }
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
