from __future__ import annotations

import os
from dataclasses import dataclass
import logging
import re
import time
from typing import Optional, Protocol

import httpx
from .phone_utils import normalize_phone_e164, mask_phone

logger = logging.getLogger("superapp.sms")

try:
    from .env_loader import ensure_loaded as _ensure_env_loaded
except Exception:  # pragma: no cover
    def _ensure_env_loaded():
        return None


class SmsBackend(Protocol):
    def send(self, phone: str, message: str) -> None:  # pragma: no cover - interface
        ...


@dataclass
class LogBackend:
    def send(self, phone: str, message: str) -> None:  # pragma: no cover - log only
        masked_phone = mask_phone(phone)
        masked_msg = _mask_code_in_message(message)
        logger.debug("OTP log backend send to=%s msg=%s", masked_phone, masked_msg)


@dataclass
class HttpBackend:
    url: str
    auth_token: Optional[str] = None
    sender_name: Optional[str] = None

    def send(self, phone: str, message: str) -> None:
        if not (self.url or "").strip():
            raise RuntimeError("SMS URL must be configured for HTTP provider")
        payload = {"to": normalize_phone_e164(phone), "message": message}
        if self.sender_name:
            payload["sender"] = self.sender_name
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        _send_with_retry(
            lambda: httpx.post(self.url, json=payload, headers=headers, timeout=5.0),
            backend_name="http",
        )


@dataclass
class SyriatelTemplateBackend:
    """Syriatel BMS template sender.

    Expects env vars to be set:
      - OTP_SYRIATEL_URL (e.g., https://bms.syriatel.sy/API/SendTemplateSMS.aspx)
      - OTP_SYRIATEL_USERNAME
      - OTP_SYRIATEL_PASSWORD
      - OTP_SYRIATEL_TEMPLATE_CODE
      - OTP_SYRIATEL_SENDER
      - OTP_SYRIATEL_TO_FORMAT (optional: 'local'|'e164', default 'local')

    Uses param_list=<code> to inject the OTP into the template.
    """

    url: str
    username: str
    password: str
    template_code: str
    sender: str
    to_format: str = "local"

    def _format_to(self, phone: str) -> str:
        fmt = (self.to_format or "local").lower()
        p = normalize_phone_e164(phone)
        # Convert E.164 +963XXXXXXXXX -> 09XXXXXXXXX if requested
        if fmt == "local":
            if p.startswith("+963") and len(p) >= 4:
                return "0" + p[4:]
        return p

    def send_code(self, phone: str, code: str) -> None:
        if not (self.url and self.username and self.password and self.template_code and self.sender):
            raise RuntimeError("Syriatel template backend not fully configured")
        to = self._format_to(phone)
        params = {
            "user_name": self.username,
            "password": self.password,
            "template_code": self.template_code,
            "param_list": code,
            "sender": self.sender,
            "to": to,
        }
        def _call():
            return httpx.get(self.url, params=params, timeout=5.0)

        def _validate(res: httpx.Response) -> None:
            if res.status_code >= 400:
                raise RuntimeError(f"Syriatel SMS failed ({res.status_code}): {res.text}")
            body = (res.text or "").strip().lower()
            if not body:
                return
            # Syriatel responds with XML/CSV-like strings. Treat known success keywords as OK.
            success_tokens = ("success", "sent", "ok", "accepted", "done")
            if not any(tok in body for tok in success_tokens):
                raise RuntimeError(f"Syriatel SMS rejected: {res.text}")

        _send_with_retry(_call, backend_name="syriatel", validator=_validate)

    def send(self, phone: str, message: str) -> None:  # fallback if only message provided
        # Try to extract a 4-8 digit code from the message
        m = re.findall(r"(\d{4,8})", message or "")
        if not m:
            raise RuntimeError("Cannot extract OTP code from message for Syriatel template backend")
        code = m[-1]
        self.send_code(phone, code)


def _resolve_backend() -> SmsBackend:
    _ensure_env_loaded()
    provider = (os.getenv("OTP_SMS_PROVIDER", "log") or "log").lower()
    if provider == "log":
        return LogBackend()
    if provider in ("http", "syriatel", "syriatel_template", "mtn"):
        # Syriatel Template API requires GET with query params; prefer dedicated backend
        if provider in ("syriatel", "syriatel_template") and (os.getenv("OTP_SYRIATEL_TEMPLATE_CODE", "").strip()):
            return SyriatelTemplateBackend(
                url=os.getenv("OTP_SYRIATEL_URL", ""),
                username=os.getenv("OTP_SYRIATEL_USERNAME", ""),
                password=os.getenv("OTP_SYRIATEL_PASSWORD", ""),
                template_code=os.getenv("OTP_SYRIATEL_TEMPLATE_CODE", ""),
                sender=os.getenv("OTP_SYRIATEL_SENDER", ""),
                to_format=os.getenv("OTP_SYRIATEL_TO_FORMAT", "local"),
            )
        if provider == "mtn":
            url = os.getenv("OTP_MTN_URL", "")
            token = os.getenv("OTP_MTN_TOKEN", "") or None
            sender = os.getenv("OTP_MTN_SENDER", "") or None
        else:
            url = os.getenv("OTP_SMS_HTTP_URL", "")
            token = os.getenv("OTP_SMS_HTTP_AUTH_TOKEN", "") or None
            sender = os.getenv("OTP_SMS_SENDER_NAME", "") or None
        return HttpBackend(url=url, auth_token=token, sender_name=sender)
    # Fallback
    return LogBackend()


def _build_message(code: str) -> str:
    tmpl = os.getenv("OTP_SMS_TEMPLATE", "Your verification code is {code}") or "Your verification code is {code}"
    try:
        return tmpl.format(code=code)
    except Exception:
        return f"Your verification code is {code}"


def send_code_via_env(phone: str, code: str) -> None:
    """Send an OTP code using provider/config from environment variables.

    This function is safe to call in any service and requires no app-specific settings.
    """
    backend = _resolve_backend()
    fallback_name = os.getenv("OTP_SMS_FALLBACK_PROVIDER", "").strip()
    fallback_backend = _resolve_backend_override(fallback_name) if fallback_name else LogBackend()
    normalized_phone = normalize_phone_e164(phone)
    msg = _build_message(code)
    try:
        backend.send(normalized_phone, msg)
        logger.debug(
            "OTP dispatched via %s to=%s code=%s",
            backend.__class__.__name__,
            mask_phone(normalized_phone),
            _mask_code(code),
        )
    except Exception as exc:
        logger.warning(
            "Primary OTP provider %s failed for %s (%s)",
            backend.__class__.__name__,
            mask_phone(normalized_phone),
            exc,
        )
        if fallback_backend is None:
            raise
        fallback_backend.send(normalized_phone, msg)
        logger.debug(
            "OTP dispatched via fallback %s to=%s code=%s",
            fallback_backend.__class__.__name__,
            mask_phone(normalized_phone),
            _mask_code(code),
        )


def _resolve_backend_override(name: str) -> Optional[SmsBackend]:
    if not name:
        return None
    prev = os.getenv("OTP_SMS_PROVIDER")
    try:
        os.environ["OTP_SMS_PROVIDER"] = name
        return _resolve_backend()
    finally:
        if prev is None:
            os.environ.pop("OTP_SMS_PROVIDER", None)
        else:
            os.environ["OTP_SMS_PROVIDER"] = prev


def _mask_code(code: str) -> str:
    if not code:
        return ""
    digits = re.sub(r"\D", "", code)
    if len(digits) <= 2:
        return "*" * len(digits)
    return "*" * (len(digits) - 2) + digits[-2:]


def _mask_code_in_message(message: str) -> str:
    if not message:
        return ""
    return re.sub(r"(\d{2,})", lambda m: _mask_code(m.group(0)), message)


def _send_with_retry(callable_fn, backend_name: str, validator=None) -> None:
    max_attempts = 3
    delay = 0.5
    for attempt in range(1, max_attempts + 1):
        try:
            res = callable_fn()
            try:
                if validator:
                    validator(res)
                else:
                    if hasattr(res, "raise_for_status"):
                        res.raise_for_status()
                return
            finally:
                if hasattr(res, "close"):
                    try:
                        res.close()
                    except Exception:
                        pass
        except Exception as exc:
            if attempt == max_attempts:
                raise
            logging.getLogger("superapp.sms").warning(
                "%s SMS attempt %s failed: %s", backend_name, attempt, exc
            )
            time.sleep(delay)
            delay *= 2
