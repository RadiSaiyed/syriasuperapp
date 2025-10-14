import hmac
import hashlib
import json
import os
from typing import Optional, Dict

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


def canonical_json(obj: dict) -> str:
    # Keep separators compact like existing code; no sort_keys for compatibility
    return json.dumps(obj, separators=(",", ":"))


def sign_internal_request_headers(payload: dict, secret: str, ts: Optional[str] = None, request_id: Optional[str] = None) -> Dict[str, str]:
    import time

    ts_val = ts or str(int(time.time()))
    msg = (ts_val + canonical_json(payload)).encode()
    sign = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    headers = {
        "X-Internal-Ts": ts_val,
        "X-Internal-Sign": sign,
        "Content-Type": "application/json",
    }
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


def _redis_client(url: Optional[str]):
    if not url or redis is None:
        return None
    try:
        return redis.from_url(url)
    except Exception:
        return None


def verify_internal_hmac_with_replay(
    ts: str,
    payload: dict,
    sign: str,
    secret: str,
    redis_url: Optional[str] = None,
    ttl_secs: int = 60,
) -> bool:
    # Compute expected HMAC (compat with existing services: ts + compact json)
    try:
        msg = (ts + canonical_json(payload)).encode()
        expect = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    except Exception:
        return False
    if not hmac.compare_digest(expect, sign):
        return False
    if ttl_secs is None or int(ttl_secs) <= 0:
        return True
    # Replay protection (optional, if Redis available)
    r = _redis_client(redis_url or os.getenv("REDIS_URL"))
    if r is None:
        return True
    key = f"hmac_replay:{sign}"
    if r.get(key):
        return False
    try:
        r.setex(key, ttl_secs, 1)
    except Exception:
        pass
    return True
