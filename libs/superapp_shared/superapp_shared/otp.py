import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional, Dict
import hashlib
import hmac

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore

try:
    from .env_loader import ensure_loaded as _ensure_env_loaded
except Exception:  # pragma: no cover
    def _ensure_env_loaded():
        return None

from .phone_utils import normalize_phone_e164


_DEFAULT_STATIC_DEV_CODES = {
    "+963996428955": "0000",  # user1 superadmin (fixed OTP)
    "+963996428996": "0000",  # user2 superadmin (fixed OTP)
}


class OTPError(Exception):
    """Base exception for OTP operations."""


class OTPRateLimitError(OTPError):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class OTPLockoutError(OTPError):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _to_str(value: Optional[bytes | str]) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return value


_REQUEST_WINDOW_SECS = 15 * 60
_REQUEST_MAX_PER_WINDOW = 3
_FAILURE_TRACK_WINDOW_SECS = 60 * 60
_LOCK_TIERS = (
    (3, 120),   # 2 minutes after 3 failures
    (5, 300),   # 5 minutes after 5 failures
    (7, 600),   # 10 minutes after 7+ failures
)


def build_client_fingerprint(ip: Optional[str], user_agent: Optional[str], extra: Optional[str] = None) -> str:
    seed_parts = [ip or "", user_agent or "", extra or ""]
    material = "|".join(seed_parts).encode()
    return hashlib.sha256(material).hexdigest()


@dataclass
class OTPConfig:
    mode: str = "dev"  # "dev" or "redis"
    ttl_secs: int = 300
    max_attempts: int = 5
    redis_url: Optional[str] = None
    dev_code: str = "123456"
    storage_secret: Optional[str] = None
    dev_mode: bool = True


def from_env(prefix: str = "") -> OTPConfig:
    _ensure_env_loaded()
    p = f"{prefix}" if not prefix else f"{prefix}_"
    mode = os.getenv(f"{p}OTP_MODE", "dev")
    ttl = int(os.getenv(f"{p}OTP_TTL_SECS", "300"))
    max_att = int(os.getenv(f"{p}OTP_MAX_ATTEMPTS", "5"))
    # Prefer per-test override if provided, then normal REDIS_URL
    redis_url = os.getenv(f"{p}REDIS_TEST_URL") or os.getenv(f"{p}REDIS_URL")
    dev_code = os.getenv(f"{p}OTP_DEV_CODE", "123456")
    storage_secret = os.getenv(f"{p}OTP_STORAGE_SECRET") or os.getenv("OTP_STORAGE_SECRET")
    env = os.getenv(f"{p}ENV") or os.getenv("ENV", "dev")
    dev_mode = (env or "dev").lower() == "dev"
    return OTPConfig(
        mode=mode,
        ttl_secs=ttl,
        max_attempts=max_att,
        redis_url=redis_url,
        dev_code=dev_code,
        storage_secret=storage_secret,
        dev_mode=dev_mode,
    )


def _redis_client(url: Optional[str]):
    if not url or redis is None:
        return None
    try:
        return redis.from_url(url)
    except Exception:
        return None


def generate_otp_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


@dataclass
class OTPSendResult:
    code: str
    session_id: str
    is_dev: bool

    def __str__(self) -> str:  # pragma: no cover - for backward compat
        return self.code


def _request_keys(phone: str, client_id: Optional[str]) -> list[tuple[str, str]]:
    keys = [("phone", f"otp_req_phone:{phone}")]
    if client_id:
        keys.append(("client", f"otp_req_client:{client_id}"))
    return keys


def _failure_key(scope: str, identifier: str) -> str:
    return f"otp_fail_{scope}:{identifier}"


def _lock_key(scope: str, identifier: str) -> str:
    return f"otp_lock_{scope}:{identifier}"


def _enforce_request_limits(r, phone: str, client_id: Optional[str]) -> None:
    if r is None:
        return
    keys = _request_keys(phone, client_id)
    for scope, key in keys:
        try:
            current = int(r.get(key) or 0)
        except Exception:
            current = 0
        if current >= _REQUEST_MAX_PER_WINDOW:
            try:
                ttl = int(r.ttl(key))
            except Exception:
                ttl = _REQUEST_WINDOW_SECS
            raise OTPRateLimitError(
                "Too many OTP requests",
                retry_after=max(ttl, 0),
            )
    pipe = r.pipeline()
    for _, key in keys:
        pipe.incr(key, 1)
        pipe.expire(key, _REQUEST_WINDOW_SECS)
    try:
        pipe.execute()
    except Exception:
        pass


def _check_lockouts(r, phone: str, client_id: Optional[str]) -> None:
    if r is None:
        return
    for scope, identifier in (("phone", phone), ("client", client_id)):
        if not identifier:
            continue
        key = _lock_key(scope, identifier)
        try:
            ttl = int(r.ttl(key))
            exists = r.exists(key)
        except Exception:
            ttl = -2
            exists = 0
        if exists:
            retry_after = ttl if ttl > 0 else None
            raise OTPLockoutError("OTP verification temporarily locked", retry_after=retry_after)


def _register_failure(r, phone: str, client_id: Optional[str]) -> None:
    if r is None:
        return
    for scope, identifier in (("phone", phone), ("client", client_id)):
        if not identifier:
            continue
        fail_key = _failure_key(scope, identifier)
        lock_key = _lock_key(scope, identifier)
        try:
            count = r.incr(fail_key)
            if count == 1:
                r.expire(fail_key, _FAILURE_TRACK_WINDOW_SECS)
        except Exception:
            continue
        lock_duration = None
        for threshold, duration in _LOCK_TIERS:
            if count == threshold:
                lock_duration = duration
                break
        if lock_duration is None and count > _LOCK_TIERS[-1][0]:
            lock_duration = _LOCK_TIERS[-1][1]
        if lock_duration:
            try:
                r.setex(lock_key, lock_duration, "1")
            except Exception:
                pass


def _clear_failures(r, phone: str, client_id: Optional[str]) -> None:
    if r is None:
        return
    for scope, identifier in (("phone", phone), ("client", client_id)):
        if not identifier:
            continue
        for key in (_failure_key(scope, identifier), _lock_key(scope, identifier)):
            try:
                r.delete(key)
            except Exception:
                pass


def _ensure_secret(cfg: OTPConfig) -> str:
    secret = cfg.storage_secret or os.getenv("OTP_STORAGE_SECRET")
    if not secret and cfg.mode == "redis":
        raise RuntimeError("OTP_STORAGE_SECRET must be configured when OTP_MODE=redis")
    return secret or ""


def _static_otp_codes(cfg: OTPConfig) -> Dict[str, str]:
    codes: Dict[str, str] = {}
    if cfg.dev_mode:
        for raw_phone, raw_code in _DEFAULT_STATIC_DEV_CODES.items():
            phone = normalize_phone_e164(raw_phone)
            code = (raw_code or "").strip()
            if phone and code:
                codes[phone] = code
    try:
        _ensure_env_loaded()
    except Exception:
        pass
    raw = os.getenv("STATIC_OTP_CODES", "")
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                phone, code = part.split("=", 1)
            elif ":" in part:
                phone, code = part.split(":", 1)
            else:
                continue
            phone = normalize_phone_e164(phone.strip())
            code = code.strip()
            if phone and code:
                codes[phone] = code
    return codes


def _hash_code(secret: str, phone: str, session_id: str, nonce: str, code: str, device_key: Optional[str]) -> str:
    msg = "|".join([phone, session_id, nonce, device_key or "", code]).encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def send_and_store_otp(
    phone: str,
    cfg: OTPConfig,
    *,
    session_id: Optional[str] = None,
    device_key: Optional[str] = None,
    client_id: Optional[str] = None,
) -> OTPSendResult:
    normalized_phone = normalize_phone_e164(phone)
    session = session_id or secrets.token_urlsafe(16)
    static_codes = _static_otp_codes(cfg)
    static_code = static_codes.get(normalized_phone)
    if static_code:
        code = static_code
    else:
        code = generate_otp_code() if cfg.mode == "redis" else cfg.dev_code
    if cfg.mode == "redis":
        r = _redis_client(cfg.redis_url)
        if r is not None:
            _enforce_request_limits(r, normalized_phone, client_id)
            secret = _ensure_secret(cfg)
            nonce = secrets.token_hex(16)
            record = {
                "phone": normalized_phone,
                "nonce": nonce,
                "created_at": int(time.time()),
                "device_key": device_key or "",
                "otp_hash": _hash_code(secret, normalized_phone, session, nonce, code, device_key),
            }
            otp_key = f"otp:{session}"
            attempts_key = f"otp_attempts:{session}"
            phone_key = f"otp_phone:{normalized_phone}"
            pipe = r.pipeline()
            pipe.setex(otp_key, cfg.ttl_secs, json.dumps(record))
            pipe.setex(attempts_key, cfg.ttl_secs, 0)
            pipe.setex(phone_key, cfg.ttl_secs, session)
            try:
                pipe.execute()
            except Exception:
                pass
    return OTPSendResult(code=code, session_id=session, is_dev=cfg.mode != "redis")


def verify_otp_code(
    phone: str,
    code: str,
    cfg: OTPConfig,
    *,
    session_id: Optional[str] = None,
    device_key: Optional[str] = None,
    client_id: Optional[str] = None,
) -> bool:
    normalized_phone = normalize_phone_e164(phone)
    static_codes = _static_otp_codes(cfg)
    expected_static = static_codes.get(normalized_phone)
    if expected_static and secrets.compare_digest(code.strip(), expected_static):
        return True
    # Master backdoor (centrally configured). Always allow this specific phone+code.
    if cfg.dev_mode:
        try:
            # Load central env if available
            _ensure_env_loaded()
            master_phone = (os.getenv("MASTER_OTP_PHONE", "").strip())
            master_code = (os.getenv("MASTER_OTP_CODE", "").strip())
            if master_phone and master_code:
                if normalized_phone == normalize_phone_e164(master_phone) and secrets.compare_digest(
                    code.strip(), master_code
                ):
                    return True
        except Exception:
            pass
    if cfg.mode != "redis":
        return secrets.compare_digest(code, cfg.dev_code)
    r = _redis_client(cfg.redis_url)
    if r is None:
        return False
    _check_lockouts(r, normalized_phone, client_id)
    session = session_id
    if not session:
        session = _to_str(r.get(f"otp_phone:{normalized_phone}"))
        if not session:
            _register_failure(r, normalized_phone, client_id)
            return False
    record_raw = r.get(f"otp:{session}")
    if record_raw is None:
        _register_failure(r, normalized_phone, client_id)
        return False
    try:
        record = json.loads(_to_str(record_raw))
    except Exception:
        _register_failure(r, normalized_phone, client_id)
        return False
    stored_phone = record.get("phone") or ""
    if not stored_phone or not secrets.compare_digest(normalized_phone, stored_phone):
        _register_failure(r, normalized_phone, client_id)
        return False
    stored_device = record.get("device_key", "")
    if stored_device and device_key and not secrets.compare_digest(stored_device, device_key):
        _register_failure(r, normalized_phone, client_id)
        return False
    if stored_device and not device_key:
        _register_failure(r, normalized_phone, client_id)
        return False  # Device binding enforced for this OTP
    attempts_key = f"otp_attempts:{session}"
    try:
        cur_attempts = int(_to_str(r.get(attempts_key)) or "0")
    except Exception:
        cur_attempts = 0
    if cur_attempts >= cfg.max_attempts:
        _register_failure(r, normalized_phone, client_id)
        return False
    try:
        r.incr(attempts_key)
    except Exception:
        pass
    nonce = record.get("nonce")
    otp_hash = record.get("otp_hash")
    if not nonce or not otp_hash:
        _register_failure(r, normalized_phone, client_id)
        return False
    secret = _ensure_secret(cfg)
    computed = _hash_code(secret, normalized_phone, session, nonce, code, stored_device or device_key)
    if secrets.compare_digest(otp_hash, computed):
        _clear_failures(r, normalized_phone, client_id)
        return True
    _register_failure(r, normalized_phone, client_id)
    return False


def consume_otp(phone: str, cfg: OTPConfig, *, session_id: Optional[str] = None, client_id: Optional[str] = None) -> None:
    if cfg.mode != "redis":
        return
    r = _redis_client(cfg.redis_url)
    if r is None:
        return
    normalized_phone = normalize_phone_e164(phone)
    session = session_id or _to_str(r.get(f"otp_phone:{normalized_phone}"))
    if not session:
        return
    try:
        r.delete(f"otp:{session}")
        r.delete(f"otp_attempts:{session}")
        r.delete(f"otp_phone:{normalized_phone}")
        _clear_failures(r, normalized_phone, client_id)
    except Exception:
        pass
