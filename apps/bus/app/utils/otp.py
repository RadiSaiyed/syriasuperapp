from superapp_shared.otp import (
    OTPConfig,
    OTPSendResult,
    send_and_store_otp as _send,
    verify_otp_code as _verify,
    consume_otp as _consume,
    from_env as _from_env,
)
from superapp_shared.sms_provider import send_code_via_env
from ..config import settings


def _cfg() -> OTPConfig:
    return _from_env()


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
    result = _send(phone, _cfg(), session_id=session_id, device_key=device_key, client_id=client_id)
    try:
        # Send via configured provider (log/http/syriatel/mtn)
        send_code_via_env(phone, result.code)
    except Exception:
        # Fail open in dev mode only
        if settings.OTP_MODE != "dev":
            raise
    return result


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


def consume_otp(phone: str, *, session_id: str | None = None, client_id: str | None = None) -> None:
    _consume(phone, _cfg(), session_id=session_id, client_id=client_id)
