from __future__ import annotations

import logging
from functools import lru_cache

from superapp_shared import otp as shared_otp
from superapp_shared.otp import OTPSendResult

from .config import settings
from .sms_provider import get_sms_provider

logger = logging.getLogger("taxi.otp")


@lru_cache(maxsize=1)
def _otp_config() -> shared_otp.OTPConfig:
    return shared_otp.from_env()


def send_and_store_otp(
    phone: str,
    *,
    session_id: str | None = None,
    device_key: str | None = None,
    client_id: str | None = None,
) -> OTPSendResult:
    cfg = _otp_config()
    result = shared_otp.send_and_store_otp(
        phone,
        cfg,
        session_id=session_id,
        device_key=device_key,
        client_id=client_id,
    )
    provider = get_sms_provider()
    try:
        provider.send_code(phone, result.code)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to send OTP via %s", provider, exc_info=exc)
        if cfg.mode != "redis":
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
    cfg = _otp_config()
    valid = shared_otp.verify_otp_code(
        phone,
        code,
        cfg,
        session_id=session_id,
        device_key=device_key,
        client_id=client_id,
    )
    if valid:
        shared_otp.consume_otp(phone, cfg, session_id=session_id, client_id=client_id)
    return valid


def consume_otp(
    phone: str,
    *,
    session_id: str | None = None,
    client_id: str | None = None,
) -> None:
    cfg = _otp_config()
    shared_otp.consume_otp(phone, cfg, session_id=session_id, client_id=client_id)
