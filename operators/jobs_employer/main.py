from fastapi import FastAPI, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

# Import Jobs domain via PYTHONPATH=apps/jobs
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
from app.routers import employer as employer_router
from app.auth import get_current_user
from app.database import get_db
from app.models import Company, Job, Application
from fastapi import HTTPException, status, Depends


def create_app() -> FastAPI:
    app = FastAPI(title="Jobs Employer API", version="0.1.0")

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
            {"name": "employer", "description": "Employer endpoints: company, jobs, applications"},
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
    app.include_router(employer_router.router)
    @app.get("/info", tags=["about"])
    def info():
        return {"service": "Jobs Employer API", "version": "0.1.0", "env": settings.ENV}

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
    def me(user = Depends(get_current_user), db = Depends(get_db)):
        if user.role != "employer":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employer only")
        comp = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
        jobs = db.query(Job).filter(Job.company_id == (comp.id if comp else None)).count() if comp else 0
        apps = 0
        if comp:
            job_ids = [j.id for j in db.query(Job).filter(Job.company_id == comp.id).all()]
            if job_ids:
                apps = db.query(Application).filter(Application.job_id.in_(job_ids)).count()
        from datetime import datetime, timedelta
        now = datetime.utcnow(); since7 = now - timedelta(days=7); since30 = now - timedelta(days=30)
        j7 = a7 = j30 = a30 = 0
        if comp:
            j7 = db.query(Job).filter(Job.company_id == comp.id, Job.created_at >= since7).count()
            j30 = db.query(Job).filter(Job.company_id == comp.id, Job.created_at >= since30).count()
            if job_ids:
                a7 = db.query(Application).filter(Application.job_id.in_(job_ids), Application.created_at >= since7).count()
                a30 = db.query(Application).filter(Application.job_id.in_(job_ids), Application.created_at >= since30).count()
        return {
            "user": {"id": str(user.id), "phone": user.phone, "name": user.name},
            "company": None if not comp else {"id": str(comp.id), "name": comp.name},
            "jobs_total": int(jobs),
            "applications_total": int(apps),
            "metrics": {"7d": {"jobs_total": int(j7), "applications_total": int(a7)}, "30d": {"jobs_total": int(j30), "applications_total": int(a30)}},
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
    <h3>Employer</h3>
    <div>
      <input id=\"cname\" placeholder=\"company name\"> <input id=\"cdesc\" placeholder=\"description\" size=\"32\"> <button onclick=\"createCompany()\">Create Company</button> <button onclick=\"getCompany()\">Get Company</button>
    </div>
    <div>
      <input id=\"title\" placeholder=\"job title\"> <input id=\"loc\" placeholder=\"location\"> <input id=\"salary\" type=\"number\" placeholder=\"salary_cents\"> <input id=\"cat\" placeholder=\"category\"> <input id=\"etype\" placeholder=\"employment_type\"> <label><input id=\"remote\" type=\"checkbox\"> remote</label>
      <button onclick=\"createJob()\">Create Job</button> <button onclick=\"listJobs()\">My Jobs</button>
    </div>
    <div>
      <input id=\"jid\" placeholder=\"job_id\" size=\"36\"> <button onclick=\"listApplications()\">Applications</button>
      <input id=\"appId\" placeholder=\"application_id\" size=\"36\"> <select id=\"appSt\"><option>applied</option><option>reviewed</option><option>accepted</option><option>rejected</option></select> <button onclick=\"setAppStatus()\">Set Status</button>
      <select id=\"jobSt\"><option>open</option><option>closed</option></select> <button onclick=\"setJobStatus()\">Set Job Status</button>
    </div>
    <div>
      <label>Update Tags (comma-separated)</label> <input id=\"tagsUpd\" size=\"40\" placeholder=\"e.g. python,remote\"> <button onclick=\"setJobTags()\">Update Tags</button>
    </div>
    <pre id=\"eout\"></pre>
  </div>
</div>
<script>
const out=document.getElementById('out');
const eout=document.getElementById('eout');
function auth(json=false){ const t=document.getElementById('tok').value.trim(); const h=t?{Authorization:'Bearer '+t}:{ }; if(json) h['Content-Type']='application/json'; return h; }
async function info(){ const r=await fetch('/info'); out.textContent=await r.text(); }
async function health(){ const r=await fetch('/health'); out.textContent=await r.text(); }
async function me(){ const r=await fetch('/me',{headers: auth()}); out.textContent=await r.text(); }
async function createCompany(){ const body={name:cname.value, description:cdesc.value}; const r=await fetch('/employer/company',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); eout.textContent=await r.text(); }
async function getCompany(){ const r=await fetch('/employer/company',{headers:auth()}); eout.textContent=await r.text(); }
async function createJob(){ const body={title:title.value, description:'', location:loc.value, salary_cents:parseInt(salary.value||'0',10), category:cat.value, employment_type:etype.value, is_remote:remote.checked, tags:[]}; const r=await fetch('/employer/jobs',{method:'POST', headers:auth(true), body: JSON.stringify(body)}); eout.textContent=await r.text(); }
async function listJobs(){ const r=await fetch('/employer/jobs',{headers:auth()}); eout.textContent=await r.text(); }
async function listApplications(){ const id=document.getElementById('jid').value.trim(); const r=await fetch('/employer/jobs/'+id+'/applications',{headers:auth()}); eout.textContent=await r.text(); }
async function setAppStatus(){ const id=document.getElementById('appId').value.trim(); const st=document.getElementById('appSt').value; const body={status:st}; const r=await fetch('/employer/applications/'+id,{method:'PATCH', headers:auth(true), body: JSON.stringify(body)}); eout.textContent=await r.text(); }
async function setJobStatus(){ const id=document.getElementById('jid').value.trim(); const st=document.getElementById('jobSt').value; const body={status:st}; const r=await fetch('/employer/jobs/'+id,{method:'PATCH', headers:auth(true), body: JSON.stringify(body)}); eout.textContent=await r.text(); }
async function setJobTags(){ const id=document.getElementById('jid').value.trim(); const tags=(document.getElementById('tagsUpd').value||'').split(',').map(s=>s.trim()).filter(Boolean); const body={tags: tags}; const r=await fetch('/employer/jobs/'+id,{method:'PATCH', headers:auth(true), body: JSON.stringify(body)}); eout.textContent=await r.text(); }
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
