import os
import time
import random
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import json as pyjson
import websockets
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import asyncio
try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None

try:  # Optional JWT verification (RS256 via JWKS)
    from superapp_shared.jwks_verify import decode_with_jwks as _jwks_decode
except Exception:  # pragma: no cover
    _jwks_decode = None


APP_ENV = os.getenv("APP_ENV", "dev")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8070"))

PAYMENTS_BASE_URL = os.getenv("PAYMENTS_BASE_URL", "http://host.docker.internal:8080")
REDIS_URL = os.getenv("REDIS_URL", "")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

# JWT (RS256) verification defaults to enforced in prod
JWT_JWKS_URL = os.getenv("JWT_JWKS_URL", f"{PAYMENTS_BASE_URL}/.well-known/jwks.json")
JWT_ISSUER = os.getenv("JWT_ISSUER") or None
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE") or None
JWT_ENFORCE = (os.getenv("JWT_ENFORCE", "false").lower() == "true") or (APP_ENV == "prod")

# CORS configuration (safer in prod)
_ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS") or os.getenv("COMMON_ALLOWED_ORIGINS") or ""
if _ALLOWED_ORIGINS_ENV.strip():
    ALLOWED_ORIGINS = [s.strip() for s in _ALLOWED_ORIGINS_ENV.split(",") if s.strip()]
else:
    ALLOWED_ORIGINS = ["*"] if APP_ENV != "prod" else []

# Upstream bases for path-based proxying (/<service>/...)
DEFAULT_BASES = {
    "payments": PAYMENTS_BASE_URL,
    "taxi": os.getenv("TAXI_BASE_URL", "http://host.docker.internal:8081"),
    "bus": os.getenv("BUS_BASE_URL", "http://host.docker.internal:8082"),
    "commerce": os.getenv("COMMERCE_BASE_URL", "http://host.docker.internal:8083"),
    "utilities": os.getenv("UTILITIES_BASE_URL", "http://host.docker.internal:8084"),
    "freight": os.getenv("FREIGHT_BASE_URL", "http://host.docker.internal:8085"),
    "carmarket": os.getenv("CARMARKET_BASE_URL", "http://host.docker.internal:8086"),
    "jobs": os.getenv("JOBS_BASE_URL", "http://host.docker.internal:8087"),
    "stays": os.getenv("STAYS_BASE_URL", "http://host.docker.internal:8088"),
    "doctors": os.getenv("DOCTORS_BASE_URL", "http://host.docker.internal:8089"),
    "food": os.getenv("FOOD_BASE_URL", "http://host.docker.internal:8090"),
    "chat": os.getenv("CHAT_BASE_URL", "http://host.docker.internal:8091"),
    "realestate": os.getenv("REALESTATE_BASE_URL", "http://host.docker.internal:8092"),
    "agriculture": os.getenv("AGRICULTURE_BASE_URL", "http://host.docker.internal:8093"),
    "livestock": os.getenv("LIVESTOCK_BASE_URL", "http://host.docker.internal:8094"),
    "carrental": os.getenv("CARRENTAL_BASE_URL", "http://host.docker.internal:8095"),
    "parking": os.getenv("PARKING_BASE_URL", "http://host.docker.internal:8096"),
    "parking_offstreet": os.getenv("PARKING_OFFSTREET_BASE_URL", "http://host.docker.internal:8097"),
    "flights": os.getenv("FLIGHTS_BASE_URL", "http://host.docker.internal:8098"),
    "ai_gateway": os.getenv("AI_GATEWAY_BASE_URL", "http://host.docker.internal:8099"),
}


class Feature(BaseModel):
    id: str
    title: str
    enabled: bool = True
    icon: str | None = None
    order: int | None = None


def _features_from_env() -> Optional[List[Feature]]:
    raw = os.getenv("BFF_FEATURES_JSON", "").strip()
    if raw:
        try:
            arr = pyjson.loads(raw)
            out: List[Feature] = []
            for idx, it in enumerate(arr):
                fid = str(it.get("id"))
                title = str(it.get("title", fid))
                en = bool(it.get("enabled", True))
                out.append(Feature(id=fid, title=title, enabled=en, order=idx))
            return out
        except Exception:
            pass
    csv = os.getenv("BFF_FEATURES", "").strip()
    if csv:
        out2: List[Feature] = []
        for idx, part in enumerate(csv.split(",")):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                fid, title = part.split(":", 1)
            else:
                fid, title = part, part.capitalize()
            out2.append(Feature(id=fid.strip(), title=title.strip(), enabled=True, order=idx))
        return out2
    return None


def default_features() -> List[Feature]:
    envf = _features_from_env()
    if envf is not None:
        return envf
    ids = [
        ("payments", "Payments"),
        ("taxi", "Taxi"),
        ("food", "Food"),
        ("flights", "Flights"),
        ("bus", "Bus"),
        ("chat", "Chat"),
        ("carmarket", "Car Market"),
        ("freight", "Freight"),
        ("carrental", "Car Rental"),
        ("stays", "Stays"),
        ("realestate", "Real Estate"),
        ("jobs", "Jobs"),
        ("utilities", "Utilities"),
        ("doctors", "Doctors"),
        ("commerce", "Commerce"),
        ("parking", "Parking"),
        ("garages", "Garages"),
        ("agriculture", "Agriculture"),
        ("ai", "AI Assistant"),
        ("livestock", "Livestock"),
    ]
    return [Feature(id=i, title=t, enabled=True, order=idx) for idx, (i, t) in enumerate(ids)]


app = FastAPI(title="Super‑App BFF", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- OpenTelemetry (optional; enabled when exporter endpoint present) ---
def _init_tracing_once() -> None:
    try:
        if getattr(app.state, "_otel_init", False):
            return
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or "http://localhost:4318"
        service_name = os.getenv("OTEL_SERVICE_NAME", "bff")
        # Lazy import to avoid test overhead when unused
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            "service.name": service_name,
            "deployment.environment": APP_ENV,
        })
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        # Instrument frameworks
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        app.state._otel_init = True
    except Exception:
        # fail-open; tracing optional
        app.state._otel_init = True

# Prometheus metrics (initialized on startup to avoid duplicate registration)
REQ_COUNTER = None
LAT_HIST = None

PUSH_REG: Dict[str, list[Dict[str, Any]]] = {}
TOPICS: Dict[str, set] = {}
USER_TOPICS: Dict[str, set] = {}
REDIS: Optional["redis.Redis"] = None


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    # Generate/propagate a request ID
    try:
        rid = request.headers.get("x-request-id") or _gen_request_id()
    except Exception:
        rid = None
    if rid:
        setattr(request.state, "request_id", rid)

    # Simple rate-limit per IP (Redis minute window if available; else in-memory bucket)
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    now = time.time()
    need = 0 if request.url.path.startswith("/metrics") else 1
    limited = False
    if need:
        if REDIS is not None:
            try:
                minute = int(now // 60)
                limit = int(os.getenv("RL_LIMIT_PER_MINUTE", "60"))
                key = f"bff:rl:{ip}:{minute}"
                val = await REDIS.incr(key)
                if val == 1:
                    await REDIS.expire(key, 65)
                if val > limit:
                    limited = True
            except Exception:
                limited = False
        else:
            if not hasattr(app.state, "_rl"):
                app.state._rl = {}
            b = app.state._rl.get(ip)
            cap = 60
            rate = 1.0
            if not b:
                b = {"t": now, "tokens": cap}
            else:
                delta = now - b["t"]
                b["tokens"] = min(cap, b["tokens"] + delta * rate)
                b["t"] = now
            if b["tokens"] < need:
                limited = True
            else:
                b["tokens"] -= need
            app.state._rl[ip] = b
    if limited:
        try:
            getattr(app.state, "REQ_COUNTER").labels(request.method, _metrics_path_label(request), "429").inc()
        except Exception:
            pass
        return Response(status_code=429, content="rate limited")

    path_t = _metrics_path_label(request)
    method = request.method
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        dur = time.perf_counter() - start
        status = str(getattr(request.state, "_status_code", getattr(locals().get("response", Response()), "status_code", 0)))
        try:
            # Try to attach exemplar with current trace_id if available
            exemplar = None
            try:
                from opentelemetry import trace as _trace  # type: ignore
                ctx = _trace.get_current_span().get_span_context()
                if getattr(ctx, "trace_id", 0):
                    tid = f"{ctx.trace_id:032x}"
                    exemplar = {"trace_id": tid}
            except Exception:
                exemplar = None
            h = getattr(app.state, "LAT_HIST")
            if exemplar:
                try:
                    h.labels(method, path_t).observe(dur, exemplar=exemplar)  # type: ignore[call-arg]
                except Exception:
                    h.labels(method, path_t).observe(dur)
            else:
                h.labels(method, path_t).observe(dur)
            getattr(app.state, "REQ_COUNTER").labels(method, path_t, status).inc()
        except Exception:
            pass


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp: Response = await call_next(request)
    try:
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault(
            "Permissions-Policy",
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
        )
        if request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            resp.headers.setdefault("Cache-Control", "no-store")
        else:
            resp.headers.setdefault("Cache-Control", "no-cache, max-age=0")
    except Exception:
        pass
    return resp


"""
Auth convenience (proxy to Payments): /auth/* endpoints
These are defined before the dynamic path proxy to avoid shadowing.
"""

@app.post("/auth/register")
async def bff_auth_register(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with httpx.AsyncClient() as client:
        try:
            js = await _fetch_json(client, "POST", f"{PAYMENTS_BASE_URL}/auth/register", json=payload)
        except HTTPException as e:
            # propagate error response
            detail = e.detail if isinstance(e.detail, (dict, list, str)) else str(e.detail)
            return Response(status_code=e.status_code, content=pyjson.dumps(detail), media_type="application/json")
    return Response(content=pyjson.dumps(js), media_type="application/json")


@app.post("/auth/login")
async def bff_auth_login(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with httpx.AsyncClient() as client:
        try:
            js = await _fetch_json(client, "POST", f"{PAYMENTS_BASE_URL}/auth/login", json=payload)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, (dict, list, str)) else str(e.detail)
            return Response(status_code=e.status_code, content=pyjson.dumps(detail), media_type="application/json")
    return Response(content=pyjson.dumps(js), media_type="application/json")


@app.post("/auth/dev_login")
async def bff_auth_dev_login(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with httpx.AsyncClient() as client:
        try:
            js = await _fetch_json(client, "POST", f"{PAYMENTS_BASE_URL}/auth/dev_login", json=payload)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, (dict, list, str)) else str(e.detail)
            return Response(status_code=e.status_code, content=pyjson.dumps(detail), media_type="application/json")
    return Response(content=pyjson.dumps(js), media_type="application/json")


@app.post("/auth/request_otp")
async def bff_auth_request_otp(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with httpx.AsyncClient() as client:
        try:
            js = await _fetch_json(client, "POST", f"{PAYMENTS_BASE_URL}/auth/request_otp", json=payload)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, (dict, list, str)) else str(e.detail)
            return Response(status_code=e.status_code, content=pyjson.dumps(detail), media_type="application/json")
    return Response(content=pyjson.dumps(js), media_type="application/json")


@app.post("/auth/verify_otp")
async def bff_auth_verify_otp(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    async with httpx.AsyncClient() as client:
        try:
            js = await _fetch_json(client, "POST", f"{PAYMENTS_BASE_URL}/auth/verify_otp", json=payload)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, (dict, list, str)) else str(e.detail)
            return Response(status_code=e.status_code, content=pyjson.dumps(detail), media_type="application/json")
    return Response(content=pyjson.dumps(js), media_type="application/json")

@app.on_event("startup")
async def on_startup():
    # Initialize tracing if configured
    _init_tracing_once()
    global REDIS
    # Initialize metrics once
    if not hasattr(app.state, "REQ_COUNTER"):
        try:
            app.state.REQ_COUNTER = Counter(
                "bff_requests_total",
                "Total HTTP requests",
                ["method", "path", "status"],
            )
            app.state.LAT_HIST = Histogram(
                "bff_request_latency_seconds",
                "Request latency",
                ["method", "path"],
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
            )
        except Exception:
            # ignore duplicate registration in edge cases
            pass
    if REDIS_URL and redis is not None:
        try:
            REDIS = redis.from_url(REDIS_URL, decode_responses=True)
            await REDIS.ping()
        except Exception:
            REDIS = None


@app.post("/v1/push/register")
async def register_push(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    # Enforce JWT validity in prod (configurable)
    _ensure_valid_bearer(headers.get("Authorization", ""))
    try:
        data = await request.json()
    except Exception:
        data = {}
    token = str(data.get("token", "")).strip()
    platform = (str(data.get("platform", "")).strip() or "unknown").lower()
    device_id = str(data.get("device_id", "")).strip()
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    rec = {
        "token": token,
        "platform": platform,
        "device_id": device_id,
        "at": int(time.time()),
        "ua": request.headers.get("user-agent", "")[:160],
    }
    key = f"push:user:{sub}"
    if REDIS is not None:
        try:
            await REDIS.hset(key, device_id or f"tok:{token}", pyjson.dumps(rec))
            count = await REDIS.hlen(key)
            # track user key for broadcast
            await REDIS.sadd("push:users", sub)
            return {"detail": "ok", "count": int(count), "store": "redis"}
        except Exception:
            pass
    # Fallback in-memory
    PUSH_REG.setdefault(sub, [])
    if device_id:
        PUSH_REG[sub] = [x for x in PUSH_REG[sub] if x.get("device_id") != device_id]
    PUSH_REG[sub].append(rec)
    return {"detail": "ok", "count": len(PUSH_REG.get(sub, [])), "store": "memory"}


def _decode_payload_from_bearer(authz: str) -> Optional[dict]:
    try:
        raw = authz.split()[1]
        parts = raw.split(".")
        payload = pyjson.loads(base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8"))
        return payload
    except Exception:
        return None


def _verify_bearer_payload(authz: str) -> Optional[dict]:
    # In dev/non-enforced mode, accept best-effort decoded payload
    if not JWT_ENFORCE:
        return _decode_payload_from_bearer(authz)
    if not _jwks_decode or not JWT_JWKS_URL:
        if APP_ENV != "prod":
            return _decode_payload_from_bearer(authz)
        raise HTTPException(status_code=401, detail="token verification unavailable")
    try:
        raw = authz.split()[1]
        return _jwks_decode(raw, JWT_JWKS_URL, audience=JWT_AUDIENCE, issuer=JWT_ISSUER)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}")


def _ensure_valid_bearer(authz: str) -> dict:
    p = _verify_bearer_payload(authz)
    if not isinstance(p, dict):
        raise HTTPException(status_code=401, detail="invalid token")
    return p


def _is_admin_token(authz: str) -> bool:
    # Admin if token claims include role/is_admin/permissions/scopes
    try:
        p = _verify_bearer_payload(authz) or {}
        role = str(p.get("role", "")).lower()
        if role in {"admin", "owner", "operator", "ops"}:
            return True
        if bool(p.get("is_admin", False)):
            return True
        scopes = p.get("scope") or p.get("scopes") or []
        if isinstance(scopes, str):
            scopes = [s.strip() for s in scopes.split()]  # space or comma
        perms = p.get("permissions") or []
        if isinstance(perms, str):
            perms = [s.strip() for s in perms.replace(",", " ").split()]
        bag = {*(scopes or []), *(perms or [])}
        if any(s in bag for s in {"admin", "push:admin", "push:send", "ops:admin"}):
            return True
        # Allowlist via env for phone/sub (dev push)
        allowed_phones = {s.strip() for s in os.getenv("PUSH_DEV_ALLOWED_PHONES", "").split(",") if s.strip()}
        allowed_subs = {s.strip() for s in os.getenv("PUSH_DEV_ALLOWED_SUBS", "").split(",") if s.strip()}
        if allowed_phones and str(p.get("phone", "")) in allowed_phones:
            return True
        if allowed_subs and str(p.get("sub", "")) in allowed_subs:
            return True
        # Allowlist for topics (optional)
        topics_phones = {s.strip() for s in os.getenv("PUSH_TOPICS_ALLOWED_PHONES", "").split(",") if s.strip()}
        topics_subs = {s.strip() for s in os.getenv("PUSH_TOPICS_ALLOWED_SUBS", "").split(",") if s.strip()}
        if topics_phones and str(p.get("phone", "")) in topics_phones:
            return True
        if topics_subs and str(p.get("sub", "")) in topics_subs:
            return True
    except Exception:
        return False
    return False


def _require_push_dev_access(authorization: str | None):
    if authorization is None or not authorization.strip():
        raise HTTPException(status_code=401, detail="missing bearer token")
    # Default in non‑prod: allow all unless explicitly disabled
    allow_non_prod = os.getenv("PUSH_DEV_ALLOW_ALL", "true").lower() == "true"
    if APP_ENV != "prod" and allow_non_prod:
        return
    if not _is_admin_token(authorization):
        raise HTTPException(status_code=403, detail="admin required for dev push")


@app.get("/v1/push/dev/list")
async def list_push(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    _require_push_dev_access(headers.get("Authorization"))
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    key = f"push:user:{sub}"
    if REDIS is not None:
        try:
            items = await REDIS.hgetall(key)
            regs = [pyjson.loads(v) for v in items.values()]
            return {"user": sub, "registrations": regs, "store": "redis"}
        except Exception:
            pass
    return {"user": sub, "registrations": PUSH_REG.get(sub, []), "store": "memory"}


@app.post("/v1/push/dev/send")
async def dev_send_push(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    _require_push_dev_access(headers.get("Authorization"))
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    title = str(payload.get("title", ""))
    body = str(payload.get("body", ""))
    data = payload.get("data") or {}
    if not data and payload.get("deeplink"):
        data = {"deeplink": str(payload.get("deeplink"))}

    # Collect regs
    regs: list[Dict[str, Any]] = []
    if REDIS is not None:
        try:
            items = await REDIS.hgetall(f"push:user:{sub}")
            regs = [pyjson.loads(v) for v in items.values()]
        except Exception:
            regs = []
    if not regs:
        regs = PUSH_REG.get(sub, [])

    sent = 0
    failed = 0
    for r in regs:
        tok = r.get("token") or ""
        if not tok:
            continue
        try:
            if FCM_SERVER_KEY:
                await _send_fcm(tok, title=title, body=body, data=data)
                sent += 1
            else:
                # No provider configured; simulate
                sent += 1
        except Exception:
            failed += 1
    return {"detail": "ok", "sent": sent, "failed": failed, "count": len(regs)}


@app.post("/v1/push/dev/broadcast")
async def dev_broadcast_push(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    _require_push_dev_access(headers.get("Authorization"))
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    title = str(payload.get("title", "Broadcast"))
    body = str(payload.get("body", ""))
    data = payload.get("data") or {}
    if not data and payload.get("deeplink"):
        data = {"deeplink": str(payload.get("deeplink"))}

    subs: list[str] = []
    if REDIS is not None:
        try:
            subs = list(await REDIS.smembers("push:users"))
        except Exception:
            subs = []
    if not subs:
        subs = list(PUSH_REG.keys())

    total_regs = 0
    sent = 0
    failed = 0
    for sub in subs:
        regs: list[Dict[str, Any]] = []
        if REDIS is not None:
            try:
                items = await REDIS.hgetall(f"push:user:{sub}")
                regs = [pyjson.loads(v) for v in items.values()]
            except Exception:
                regs = []
        if not regs:
            regs = PUSH_REG.get(sub, [])
        total_regs += len(regs)
        for r in regs:
            tok = r.get("token") or ""
            if not tok:
                continue
            try:
                if FCM_SERVER_KEY:
                    await _send_fcm(tok, title=title, body=body, data=data)
                    sent += 1
                else:
                    sent += 1
            except Exception:
                failed += 1
    return {"detail": "ok", "sent": sent, "failed": failed, "targets": total_regs, "users": len(subs)}


@app.post("/v1/push/topic/subscribe")
async def topic_subscribe(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    # Optional gating: require admin/allowlist when PUSH_TOPICS_ALLOW_ALL=false
    if os.getenv("PUSH_TOPICS_ALLOW_ALL", "true").lower() != "true":
        _require_push_dev_access(headers.get("Authorization"))
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    topic = (str(payload.get("topic", "")).strip()).lower()
    if not topic:
        raise HTTPException(status_code=400, detail="missing topic")
    if REDIS is not None:
        try:
            await REDIS.sadd(f"push:topic:{topic}", sub)
            await REDIS.sadd(f"push:user:{sub}:topics", topic)
            return {"detail": "ok", "topic": topic, "store": "redis"}
        except Exception:
            pass
    TOPICS.setdefault(topic, set()).add(sub)
    USER_TOPICS.setdefault(sub, set()).add(topic)
    return {"detail": "ok", "topic": topic, "store": "memory"}


@app.post("/v1/push/topic/unsubscribe")
async def topic_unsubscribe(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    if os.getenv("PUSH_TOPICS_ALLOW_ALL", "true").lower() != "true":
        _require_push_dev_access(headers.get("Authorization"))
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    topic = (str(payload.get("topic", "")).strip()).lower()
    if not topic:
        raise HTTPException(status_code=400, detail="missing topic")
    if REDIS is not None:
        try:
            await REDIS.srem(f"push:topic:{topic}", sub)
            await REDIS.srem(f"push:user:{sub}:topics", topic)
            return {"detail": "ok", "topic": topic, "store": "redis"}
        except Exception:
            pass
    TOPICS.setdefault(topic, set()).discard(sub)
    USER_TOPICS.setdefault(sub, set()).discard(topic)
    return {"detail": "ok", "topic": topic, "store": "memory"}


@app.get("/v1/push/topic/list")
async def topic_list(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    if REDIS is not None:
        try:
            items = await REDIS.smembers(f"push:user:{sub}:topics")
            return {"topics": sorted(items), "store": "redis"}
        except Exception:
            pass
    return {"topics": sorted([*USER_TOPICS.get(sub, set())]), "store": "memory"}


@app.post("/v1/push/dev/broadcast_topic")
async def dev_broadcast_topic(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    _require_push_dev_access(headers.get("Authorization"))
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    topic = (str(payload.get("topic", "")).strip()).lower()
    if not topic:
        raise HTTPException(status_code=400, detail="missing topic")
    title = str(payload.get("title", f"{topic}"))
    body = str(payload.get("body", ""))
    data = payload.get("data") or {}
    if not data and payload.get("deeplink"):
        data = {"deeplink": str(payload.get("deeplink"))}

    subs: list[str] = []
    if REDIS is not None:
        try:
            subs = list(await REDIS.smembers(f"push:topic:{topic}"))
        except Exception:
            subs = []
    if not subs:
        subs = list([s for s in (TOPICS.get(topic) or set())])

    total_regs = 0
    sent = 0
    failed = 0
    for sub in subs:
        regs: list[Dict[str, Any]] = []
        if REDIS is not None:
            try:
                items = await REDIS.hgetall(f"push:user:{sub}")
                regs = [pyjson.loads(v) for v in items.values()]
            except Exception:
                regs = []
        if not regs:
            regs = PUSH_REG.get(sub, [])
        total_regs += len(regs)
        for r in regs:
            tok = r.get("token") or ""
            if not tok:
                continue
            try:
                if FCM_SERVER_KEY:
                    await _send_fcm(tok, title=title, body=body, data=data)
                    sent += 1
                else:
                    sent += 1
            except Exception:
                failed += 1
    return {"detail": "ok", "sent": sent, "failed": failed, "targets": total_regs, "users": len(subs), "topic": topic}


async def _send_fcm(token: str, *, title: str = "", body: str = "", data: Dict[str, Any] | None = None) -> None:
    url = "https://fcm.googleapis.com/fcm/send"
    headers = {"Authorization": f"key={FCM_SERVER_KEY}", "Content-Type": "application/json"}
    payload = {
        "to": token,
        "notification": {"title": title, "body": body},
        "data": data or {},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload, timeout=5.0)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"FCM error: {r.text}")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "service": "bff",
        "env": APP_ENV,
        "time": int(time.time()),
    }


@app.get("/v1/features")
def features(request: Request) -> Response:
    feats = default_features()
    # Simple ETag from titles+ids
    payload = [f.model_dump() for f in feats]
    raw = pyjson.dumps(payload, separators=(",", ":")).encode("utf-8")
    import hashlib
    etag = hashlib.md5(raw).hexdigest()  # nosec - ETag only
    inm = request.headers.get("if-none-match")
    headers = {"ETag": etag, "Cache-Control": "public, max-age=30"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=pyjson.dumps(payload), media_type="application/json", headers=headers)


async def _fetch_json(client: httpx.AsyncClient, method: str, url: str, headers: Dict[str, str] | None = None, json: Any | None = None, request: Request | None = None) -> Any:
    # Attach request id + traceparent when missing
    headers = dict(headers or {})
    try:
        rid = getattr(request.state, "request_id", None) if request else None
        if rid and "x-request-id" not in {k.lower(): v for k, v in headers.items()}:
            headers["X-Request-ID"] = rid
    except Exception:
        pass
    if "traceparent" not in {k.lower(): v for k, v in headers.items()}:
        headers["traceparent"] = _gen_traceparent()
    r = await _request_with_retries(client, method, url, headers=headers, json=json, timeout=5.0)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)
    if not r.content:
        return {}
    return r.json()


async def _request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Dict[str, str] | None = None,
    json: Any | None = None,
    content: bytes | bytearray | memoryview | None = None,
    timeout: float = 5.0,
    attempts: int = 3,
    base_sleep: float = 0.1,
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            return await client.request(method, url, headers=headers, json=json, content=content, timeout=timeout)
        except httpx.RequestError as e:
            last_exc = e
            if i == attempts - 1:
                break
            # exponential backoff with jitter
            sleep = base_sleep * (2 ** i) + random.uniform(0, base_sleep)
            await asyncio.sleep(sleep)
    assert last_exc is not None
    raise last_exc


def _auth_headers(authz: str | None) -> Dict[str, str]:
    h: Dict[str, str] = {}
    if authz and authz.strip():
        h["Authorization"] = authz
    return h


_ME_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _gen_request_id() -> str:
    import uuid
    return uuid.uuid4().hex


def _gen_traceparent() -> str:
    # Minimal W3C traceparent: 00-<32hex trace>-<16hex span>-01
    trace_id = f"{random.getrandbits(128):032x}"
    span_id = f"{random.getrandbits(64):016x}"
    return f"00-{trace_id}-{span_id}-01"


def _metrics_path_label(request: Request) -> str:
    try:
        route = getattr(request.scope.get("route"), "path", None)
        if route:
            if route == "/{service}/{full_path:path}":
                return "/{service}/:proxy"
            return route
    except Exception:
        pass
    return request.url.path


def _decode_sub_from_bearer(authz: str) -> Optional[str]:
    try:
        p = _verify_bearer_payload(authz) or {}
        sub = str(p.get("sub", ""))
        return sub or None
    except Exception:
        return None


@app.get("/v1/me")
async def me(request: Request, authorization: str | None = Header(default=None)) -> Response:
    # Minimal aggregation: pull wallet snapshot from Payments
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    _ensure_valid_bearer(headers.get("Authorization", ""))

    # Cache key per user
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    now = time.time()
    cached = _ME_CACHE.get(sub)
    if cached and now - cached[0] < 2.0:
        return Response(content=pyjson.dumps(cached[1]), media_type="application/json", headers={"Cache-Control": "private, max-age=2"})

    async with httpx.AsyncClient() as client:
        wallet = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/wallet", headers=headers, request=request)
        # Optional tail of recent transactions (best‑effort)
        tx: List[Any] = []
        try:
            txjs = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/wallet/transactions", headers=headers, request=request)
            tx = txjs.get("transactions", [])[:5]
        except HTTPException:
            pass
        # KYC status
        kyc: Dict[str, Any] = {}
        try:
            kyc = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/kyc", headers=headers, request=request)
        except HTTPException:
            pass
        # Merchant status
        merch: Dict[str, Any] = {}
        try:
            merch = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/payments/merchant/status", headers=headers, request=request)
        except HTTPException:
            pass
        # Chat summary
        chat_sum: Dict[str, Any] = {}
        try:
            chat_base = DEFAULT_BASES.get("chat")
            chat_sum = await _fetch_json(client, "GET", f"{chat_base}/messages/conversations_summary", headers=headers, request=request)
        except Exception:
            pass

    # Support nested Payments wallet response (user + wallet)
    wallet_obj = wallet.get("wallet") if isinstance(wallet, dict) else None
    bal = None
    cur = None
    try:
        bal = (wallet_obj or {}).get("balance_cents") if isinstance(wallet_obj, dict) else wallet.get("balance_cents")
        cur = (wallet_obj or {}).get("currency_code") if isinstance(wallet_obj, dict) else wallet.get("currency_code")
    except Exception:
        bal = None
        cur = None

    out = {
        "user": {
            "wallet": wallet,
            "recent_transactions": tx,
            "kyc": kyc,
            "merchant": merch,
        },
        "services": {
            "payments": {
                "wallet_balance_cents": bal,
                "currency": cur,
            },
            "chat": chat_sum,
        },
    }
    _ME_CACHE[sub] = (now, out)
    return Response(content=pyjson.dumps(out), media_type="application/json", headers={"Cache-Control": "private, max-age=2"})


@app.get("/v1/search")
async def search(q: str, authorization: str | None = Header(default=None)) -> Response:
    """Lightweight federated search.

    MVP: query Utilities help store via AI Gateway through Utilities `/help/search`.
    """
    headers = _auth_headers(authorization)
    out: List[Dict[str, Any]] = []
    util_base = DEFAULT_BASES.get("utilities")
    try:
        async with httpx.AsyncClient() as client:
            js = await _fetch_json(client, "GET", f"{util_base}/help/search", headers=headers, json=None)
            for it in js.get("items", [])[:5]:
                out.append({
                    "service": "utilities",
                    "kind": "help",
                    "title": it.get("text", "Help"),
                    "score": it.get("score", 0.0),
                })
    except Exception:
        pass

    return Response(content=pyjson.dumps({"results": out}), media_type="application/json", headers={"Cache-Control": "public, max-age=5"})


@app.get("/v1/payments/transactions")
async def payments_transactions(authorization: str | None = Header(default=None)) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        js = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/wallet/transactions", headers=headers)
    raw = pyjson.dumps(js, separators=(",", ":")).encode("utf-8")
    import hashlib
    etag = hashlib.md5(raw).hexdigest()  # nosec - ETag only
    return Response(content=raw, media_type="application/json", headers={"ETag": etag, "Cache-Control": "private, max-age=10"})


# --- Commerce convenience with ETag ---

def _etag_for_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.md5(data).hexdigest()  # nosec - ETag only


@app.get("/v1/commerce/shops")
async def commerce_shops(authorization: str | None = Header(default=None), request: Request = None) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        shops = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/shops", headers=headers, request=request)
    raw = pyjson.dumps(shops, separators=(",", ":")).encode("utf-8")
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "public, max-age=30"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@app.get("/v1/commerce/shops/{shop_id}/products")
async def commerce_products(shop_id: str, authorization: str | None = Header(default=None), request: Request = None) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        products = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/shops/{shop_id}/products", headers=headers, request=request)
    raw = pyjson.dumps(products, separators=(",", ":")).encode("utf-8")
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "public, max-age=30"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@app.get("/v1/commerce/orders")
async def commerce_orders(authorization: str | None = Header(default=None), request: Request = None) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        orders = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/orders", headers=headers, request=request)
    raw = pyjson.dumps(orders, separators=(",", ":")).encode("utf-8")
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "private, max-age=15"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@app.get("/v1/commerce/orders/{order_id}")
async def commerce_order(order_id: str, authorization: str | None = Header(default=None), request: Request = None) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        order = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/orders/{order_id}", headers=headers, request=request)
    raw = pyjson.dumps(order, separators=(",", ":")).encode("utf-8")
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "private, max-age=30"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


# --- Stays convenience ---

@app.get("/v1/stays/properties")
async def stays_properties(city: str | None = None, type: str | None = None, q: str | None = None, request: Request = None) -> Response:
    qp = {}
    if city: qp["city"] = city
    if type: qp["type"] = type
    if q: qp["q"] = q
    async with httpx.AsyncClient() as client:
        _h = {"X-Request-ID": getattr(request, 'state', object()).__dict__.get('request_id', _gen_request_id()) if request else _gen_request_id(),
              "traceparent": _gen_traceparent()}
        r = await client.get(f"{DEFAULT_BASES['stays']}/properties", params=qp, headers=_h, timeout=5.0)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    raw = r.content or b"[]"
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "public, max-age=60"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@app.get("/v1/stays/properties/{prop_id}")
async def stays_property(prop_id: str, request: Request = None) -> Response:
    async with httpx.AsyncClient() as client:
        _h = {"X-Request-ID": getattr(request, 'state', object()).__dict__.get('request_id', _gen_request_id()) if request else _gen_request_id(),
              "traceparent": _gen_traceparent()}
        r = await client.get(f"{DEFAULT_BASES['stays']}/properties/{prop_id}", headers=_h, timeout=5.0)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    raw = r.content or b"{}"
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "public, max-age=120"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@app.get("/v1/stays/reservations")
async def stays_reservations(authorization: str | None = Header(default=None), request: Request = None) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        res = await _fetch_json(client, "GET", f"{DEFAULT_BASES['stays']}/reservations", headers=headers, request=request)
    raw = pyjson.dumps(res, separators=(",", ":")).encode("utf-8")
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "private, max-age=30"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@app.post("/v1/stays/reservations/{reservation_id}/cancel")
async def stays_reservation_cancel(reservation_id: str, authorization: str | None = Header(default=None)) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        _h = dict(headers)
        if "x-request-id" not in {k.lower(): v for k, v in _h.items()}:
            _h["X-Request-ID"] = _gen_request_id()
        if "traceparent" not in {k.lower(): v for k, v in _h.items()}:
            _h["traceparent"] = _gen_traceparent()
        r = await client.post(f"{DEFAULT_BASES['stays']}/reservations/{reservation_id}/cancel", headers=_h, timeout=5.0)
    if r.status_code >= 400:
        try:
            return Response(status_code=r.status_code, content=r.content or r.text, media_type=r.headers.get('content-type','application/json'))
        except Exception:
            raise HTTPException(status_code=r.status_code, detail=r.text)
    return Response(content=r.content or b"{}", media_type=r.headers.get('content-type','application/json'))


@app.get("/v1/stays/favorites")
async def stays_favorites(authorization: str | None = Header(default=None), request: Request = None) -> Response:
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")
    async with httpx.AsyncClient() as client:
        try:
            fav = await _fetch_json(client, "GET", f"{DEFAULT_BASES['stays']}/properties/favorites", headers=headers, request=request)
        except HTTPException as e:
            # In dev, degrade to empty list to not block basic flows
            if APP_ENV != "prod":
                fav = {"favorites": []}
            else:
                raise
    raw = pyjson.dumps(fav, separators=(",", ":")).encode("utf-8")
    etag = _etag_for_bytes(raw)
    inm = request.headers.get("if-none-match") if request else None
    headers = {"ETag": etag, "Cache-Control": "private, max-age=60"}
    if inm == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


## proxy_service moved to end of file to avoid route shadowing


@app.websocket("/{service}/ws")
async def ws_proxy(service: str, websocket: WebSocket):
    base = DEFAULT_BASES.get(service)
    if not base:
        await websocket.close(code=4404)
        return
    await websocket.accept()

    # Build upstream WS URL
    upstream = base.replace("http://", "ws://").replace("https://", "wss://")
    # Preserve token query string if provided by client
    qs = websocket.url.query
    upstream_url = f"{upstream}/ws"
    if qs:
        upstream_url = f"{upstream_url}?{qs}"

    try:
        async with websockets.connect(upstream_url) as upstream_ws:
            async def client_to_upstream():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await upstream_ws.send(msg)
                except WebSocketDisconnect:
                    try:
                        await upstream_ws.close()
                    except Exception:
                        pass

            async def upstream_to_client():
                try:
                    while True:
                        msg = await upstream_ws.recv()
                        if isinstance(msg, (bytes, bytearray)):
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(str(msg))
                except Exception:
                    try:
                        await websocket.close()
                    except Exception:
                        pass

            import asyncio
            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@app.api_route("/{service}/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_service(service: str, full_path: str, request: Request) -> Any:
    base = DEFAULT_BASES.get(service)
    if not base:
        raise HTTPException(status_code=404, detail="unknown service")

    # Build upstream URL with original query string
    qs = request.url.query
    url = f"{base}/{full_path}"
    if qs:
        url = f"{url}?{qs}"

    # Forward selected headers (auth, content-type, idempotency, custom x-*, request-id/trace)
    fwd_headers: Dict[str, str] = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in ("authorization", "content-type", "accept", "idempotency-key") or lk.startswith("x-"):
            fwd_headers[k] = v
    # Ensure a request id exists
    if "x-request-id" not in {k.lower(): v for k, v in fwd_headers.items()}:
        rid = getattr(request.state, "request_id", None) or _gen_request_id()
        fwd_headers["X-Request-ID"] = rid
    # Traceparent
    if "traceparent" not in {k.lower(): v for k, v in fwd_headers.items()}:
        fwd_headers["traceparent"] = _gen_traceparent()
    # X-Forwarded-For best-effort
    try:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
        if ip:
            fwd_headers.setdefault("X-Forwarded-For", ip)
    except Exception:
        pass

    body = await request.body()
    method = request.method.upper()
    async with httpx.AsyncClient() as client:
        try:
            resp = await _request_with_retries(client, method, url, headers=fwd_headers, content=body, timeout=10.0)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=str(e))

    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", None))


def main() -> None:
    import uvicorn
    RELOAD = os.getenv("APP_RELOAD", "false").lower() == "true"
    uvicorn.run("apps.bff.app.main:app", host=APP_HOST, port=APP_PORT, reload=RELOAD)


if __name__ == "__main__":
    main()
## Auth convenience block moved above dynamic proxy
