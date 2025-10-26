import os
import hashlib


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    v = os.getenv(name)
    if v is None:
        return list(default or [])
    parts = [p.strip() for p in v.split(",")]
    return [p for p in parts if p]


class OTPError(Exception):
    pass


class OTPRateLimitError(OTPError):
    def __init__(self, retry_after: int = 60):
        super().__init__("otp_rate_limited")
        self.retry_after = retry_after


class OTPLockoutError(OTPError):
    def __init__(self, retry_after: int = 300):
        super().__init__("otp_locked")
        self.retry_after = retry_after


def build_client_fingerprint(ip: str | None, user_agent: str | None) -> str:
    raw = f"{ip or ''}|{user_agent or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()

