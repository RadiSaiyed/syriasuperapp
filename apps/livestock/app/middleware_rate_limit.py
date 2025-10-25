from superapp_shared.rate_limit import SlidingWindowLimiter  # re-export for local imports
from superapp_shared.rate_limit import RedisRateLimiter  # re-export for local imports
from superapp_shared.otp import (
    OTPConfig,
    OTPSendResult,
    send_and_store_otp as _send,
    verify_otp_code as _verify,
    consume_otp as _consume,
)
from .config import settings


def _cfg() -> OTPConfig:
    return OTPConfig(
        mode=settings.OTP_MODE,
        ttl_secs=settings.OTP_TTL_SECS,
        max_attempts=settings.OTP_MAX_ATTEMPTS,
        redis_url=getattr(settings, "REDIS_URL", None),
        dev_mode=getattr(settings, "DEV_MODE", True),
    )


def generate_otp_code() -> str:
    from superapp_shared.otp import generate_otp_code as gen
    return gen()


def send_and_store_otp(
    phone: str,
    *,
    session_id: str | None = None,
    device_key: str | None = None,
    client_id: str | None = None,
) -> OTPSendResult:
    return _send(phone, _cfg(), session_id=session_id, device_key=device_key, client_id=client_id)


def verify_otp_code(
    phone: str,
    code: str,
    *,
    session_id: str | None = None,
    device_key: str | None = None,
    client_id: str | None = None,
) -> bool:
    return _verify(
        phone,
        code,
        _cfg(),
        session_id=session_id,
        device_key=device_key,
        client_id=client_id,
    )


def consume_otp(
    phone: str,
    *,
    session_id: str | None = None,
    client_id: str | None = None,
) -> None:
    _consume(phone, _cfg(), session_id=session_id, client_id=client_id)
