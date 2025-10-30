import os
import time
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


APP_ENV = os.getenv("APP_ENV", "dev")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8070"))

PAYMENTS_BASE_URL = os.getenv("PAYMENTS_BASE_URL", "http://host.docker.internal:8080")
REDIS_URL = os.getenv("REDIS_URL", "")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

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


def default_features() -> List[Feature]:
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics (initialized on startup to avoid duplicate registration)
REQ_COUNTER = None
LAT_HIST = None

PUSH_REG: Dict[str, list[Dict[str, Any]]] = {}
TOPICS: Dict[str, set] = {}
USER_TOPICS: Dict[str, set] = {}
REDIS: Optional["redis.Redis"] = None


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    # Simple in-memory token-bucket rate limit per IP (best-effort)
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    if not hasattr(app.state, "_rl"):
        app.state._rl = {}
    b = app.state._rl.get(ip)
    now = time.time()
    cap = 60  # 60 tokens
    rate = 1.0  # refill per second
    if not b:
        b = {"t": now, "tokens": cap}
    else:
        delta = now - b["t"]
        b["tokens"] = min(cap, b["tokens"] + delta * rate)
        b["t"] = now
    need = 1
    if request.url.path.startswith("/metrics"):
        need = 0
    if b["tokens"] < need:
        try:
            getattr(app.state, "REQ_COUNTER").labels(request.method, request.url.path, "429").inc()
        except Exception:
            pass
        return Response(status_code=429, content="rate limited")
    b["tokens"] -= need
    app.state._rl[ip] = b

    path_t = request.url.path
    method = request.method
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        dur = time.perf_counter() - start
        status = str(getattr(request.state, "_status_code", getattr(locals().get("response", Response()), "status_code", 0)))
        try:
            getattr(app.state, "LAT_HIST").labels(method, path_t).observe(dur)
            getattr(app.state, "REQ_COUNTER").labels(method, path_t, status).inc()
        except Exception:
            pass


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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


def _is_admin_token(authz: str) -> bool:
    # Admin if token claims include role/is_admin/permissions/scopes
    try:
        p = _decode_payload_from_bearer(authz) or {}
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
        # Allowlist via env for phone/sub
        allowed_phones = {s.strip() for s in os.getenv("PUSH_DEV_ALLOWED_PHONES", "").split(",") if s.strip()}
        allowed_subs = {s.strip() for s in os.getenv("PUSH_DEV_ALLOWED_SUBS", "").split(",") if s.strip()}
        if allowed_phones and str(p.get("phone", "")) in allowed_phones:
            return True
        if allowed_subs and str(p.get("sub", "")) in allowed_subs:
            return True
    except Exception:
        return False
    return False


def _require_push_dev_access(authorization: str | None):
    if authorization is None or not authorization.strip():
        raise HTTPException(status_code=401, detail="missing bearer token")
    # Default: require admin unless explicitly allowed via env
    allow_non_prod = os.getenv("PUSH_DEV_ALLOW_ALL", "false").lower() == "true"
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


async def _fetch_json(client: httpx.AsyncClient, method: str, url: str, headers: Dict[str, str] | None = None, json: Any | None = None) -> Any:
    r = await client.request(method, url, headers=headers, json=json, timeout=5.0)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)
    if not r.content:
        return {}
    return r.json()


def _auth_headers(authz: str | None) -> Dict[str, str]:
    h: Dict[str, str] = {}
    if authz and authz.strip():
        h["Authorization"] = authz
    return h


_ME_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _decode_sub_from_bearer(authz: str) -> Optional[str]:
    try:
        raw = authz.split()[1]
        parts = raw.split(".")
        payload = pyjson.loads(base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8"))
        sub = str(payload.get("sub", ""))
        return sub or None
    except Exception:
        return None


@app.get("/v1/me")
async def me(request: Request, authorization: str | None = Header(default=None)) -> Response:
    # Minimal aggregation: pull wallet snapshot from Payments
    headers = _auth_headers(authorization)
    if "Authorization" not in headers:
        raise HTTPException(status_code=401, detail="missing bearer token")

    # Cache key per user
    sub = _decode_sub_from_bearer(headers.get("Authorization", "")) or "anon"
    now = time.time()
    cached = _ME_CACHE.get(sub)
    if cached and now - cached[0] < 2.0:
        return Response(content=pyjson.dumps(cached[1]), media_type="application/json", headers={"Cache-Control": "private, max-age=2"})

    async with httpx.AsyncClient() as client:
        wallet = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/wallet", headers=headers)
        # Optional tail of recent transactions (best‑effort)
        tx: List[Any] = []
        try:
            txjs = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/wallet/transactions", headers=headers)
            tx = txjs.get("transactions", [])[:5]
        except HTTPException:
            pass
        # KYC status
        kyc: Dict[str, Any] = {}
        try:
            kyc = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/kyc", headers=headers)
        except HTTPException:
            pass
        # Merchant status
        merch: Dict[str, Any] = {}
        try:
            merch = await _fetch_json(client, "GET", f"{PAYMENTS_BASE_URL}/payments/merchant/status", headers=headers)
        except HTTPException:
            pass
        # Chat summary
        chat_sum: Dict[str, Any] = {}
        try:
            chat_base = DEFAULT_BASES.get("chat")
            chat_sum = await _fetch_json(client, "GET", f"{chat_base}/messages/conversations_summary", headers=headers)
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
        shops = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/shops", headers=headers)
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
        products = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/shops/{shop_id}/products", headers=headers)
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
        orders = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/orders", headers=headers)
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
        order = await _fetch_json(client, "GET", f"{DEFAULT_BASES['commerce']}/orders/{order_id}", headers=headers)
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
        r = await client.get(f"{DEFAULT_BASES['stays']}/properties", params=qp, timeout=5.0)
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
        r = await client.get(f"{DEFAULT_BASES['stays']}/properties/{prop_id}", timeout=5.0)
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
        res = await _fetch_json(client, "GET", f"{DEFAULT_BASES['stays']}/reservations", headers=headers)
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
        r = await client.post(f"{DEFAULT_BASES['stays']}/reservations/{reservation_id}/cancel", headers=headers, timeout=5.0)
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
            fav = await _fetch_json(client, "GET", f"{DEFAULT_BASES['stays']}/properties/favorites", headers=headers)
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

    # Forward selected headers (auth, content-type, idempotency, custom x-*)
    fwd_headers: Dict[str, str] = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in ("authorization", "content-type", "accept", "idempotency-key") or lk.startswith("x-"):
            fwd_headers[k] = v

    body = await request.body()
    method = request.method.upper()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(method, url, headers=fwd_headers, content=body, timeout=10.0)
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
