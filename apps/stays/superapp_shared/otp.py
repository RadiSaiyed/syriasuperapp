from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class OTPConfig:
    mode: str = "dev"  # dev|redis (stub)
    ttl_secs: int = 300
    max_attempts: int = 5


@dataclass
class OTPSendResult:
    session_id: str
    code: str


def from_env() -> OTPConfig:
    return OTPConfig(
        mode=os.getenv("OTP_MODE", "dev"),
        ttl_secs=int(os.getenv("OTP_TTL_SECS", "300")),
        max_attempts=int(os.getenv("OTP_MAX_ATTEMPTS", "5")),
    )


def generate_otp_code() -> str:
    return "123456"


def send_and_store_otp(phone: str, cfg: OTPConfig, *, session_id: Optional[str] = None, device_key: Optional[str] = None, client_id: Optional[str] = None) -> OTPSendResult:
    return OTPSendResult(session_id=session_id or "dev", code=generate_otp_code())


def verify_otp_code(phone: str, code: str, cfg: OTPConfig, *, session_id: Optional[str] = None, device_key: Optional[str] = None, client_id: Optional[str] = None) -> bool:
    return code == generate_otp_code()


def consume_otp(phone: str, cfg: OTPConfig, *, session_id: Optional[str] = None, client_id: Optional[str] = None) -> None:
    return None

