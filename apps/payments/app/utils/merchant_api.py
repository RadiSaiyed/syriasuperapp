import hmac
import hashlib
import time
from typing import Optional, Tuple
import os
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore
from sqlalchemy.orm import Session
from ..models import MerchantApiKey


def _get_key(db: Session, key_id: str) -> Optional[MerchantApiKey]:
    return db.query(MerchantApiKey).filter(MerchantApiKey.key_id == key_id).one_or_none()


def verify_request(db: Session, key_id: str, sign: str, ts: str, path: str, body_bytes: bytes) -> Optional[str]:
    """Verify HMAC signature for merchant API request.
    Returns user_id if valid else None.
    Signature is HMAC SHA256 over: ts + path + body (raw), hex-encoded.
    ts must be within +/- 5 minutes.
    """
    try:
        ts_i = int(ts)
    except Exception:
        return None
    if abs(int(time.time()) - ts_i) > 300:
        return None
    key = _get_key(db, key_id)
    if key is None:
        return None
    msg = (ts + path).encode() + body_bytes
    expect = hmac.new(key.secret.encode(), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sign):
        return None
    # Optional replay protection using Redis (if configured)
    if redis is not None:
        try:
            r = redis.from_url(os.getenv("REDIS_URL", ""))
        except Exception:
            r = None
        if r is not None:
            key_replay = f"merchant_hmac_replay:{key_id}:{sign}"
            if r.get(key_replay):
                return None
            try:
                r.setex(key_replay, 300, 1)  # 5 minutes
            except Exception:
                pass
    return str(key.user_id)
