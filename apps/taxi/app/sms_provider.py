from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from .config import settings

logger = logging.getLogger("taxi.sms")


class SmsBackend(Protocol):
    def send(self, phone: str, message: str) -> None:
        ...


@dataclass
class LogBackend:
    def send(self, phone: str, message: str) -> None:  # pragma: no cover - log only
        logger.info("SMS to %s: %s", phone, message)


@dataclass
class HttpBackend:
    url: str
    auth_token: str | None = None
    sender_name: str | None = None

    def send(self, phone: str, message: str) -> None:
        if not self.url:
            raise RuntimeError("OTP_SMS_HTTP_URL must be configured for http SMS provider")
        payload = {
            "to": phone,
            "message": message,
        }
        if self.sender_name:
            payload["sender"] = self.sender_name
        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        with httpx.Client(timeout=10.0) as client:
            res = client.post(self.url, json=payload, headers=headers)
            if res.status_code >= 400:
                raise RuntimeError(f"SMS HTTP send failed ({res.status_code}): {res.text}")


_provider: SmsBackend | None = None


def _build_message(code: str) -> str:
    template = settings.OTP_SMS_TEMPLATE or "Your Taxi verification code is {code}"
    return template.format(code=code)


def get_sms_provider() -> "SmsProvider":
    global _provider
    if _provider is None:
        mode = (settings.OTP_SMS_PROVIDER or "log").lower()
        if mode == "http":
            _provider = HttpBackend(
                url=settings.OTP_SMS_HTTP_URL,
                auth_token=settings.OTP_SMS_HTTP_AUTH_TOKEN or None,
                sender_name=settings.OTP_SMS_SENDER_NAME or None,
            )
        elif mode == "log":
            _provider = LogBackend()
        else:
            raise RuntimeError(f"Unsupported OTP_SMS_PROVIDER '{mode}'")
    return SmsProvider(_provider)


@dataclass
class SmsProvider:
    backend: SmsBackend

    def send_code(self, phone: str, code: str) -> None:
        message = _build_message(code)
        try:
            self.backend.send(phone, message)
        except Exception:
            logger.exception("SMS backend failure for %s", type(self.backend).__name__)
            raise

    def __repr__(self) -> str:  # pragma: no cover - helper for logging
        return f"SmsProvider({type(self.backend).__name__})"
