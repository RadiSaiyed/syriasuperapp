from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user
from ..config import settings
from ..models import User
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/wallet", tags=["wallet"])


def _require_payments_ready() -> None:
    if not settings.PAYMENTS_BASE_URL or not settings.PAYMENTS_INTERNAL_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments service unavailable",
        )


@router.get("/balance")
def get_wallet_balance(user: User = Depends(get_current_user)) -> dict[str, object]:
    """
    Proxy the rider's Payments wallet balance so the rider app can display
    up-to-date funds without maintaining a separate balance.
    """
    _require_payments_ready()
    payload = {"phone": user.phone}
    headers = sign_internal_request_headers(payload, settings.PAYMENTS_INTERNAL_SECRET)
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(
                f"{settings.PAYMENTS_BASE_URL}/internal/wallet",
                params={"phone": user.phone},
                headers=headers,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"payments_wallet_unreachable: {exc}",
        ) from exc
    if res.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"payments_wallet_error: {res.text}",
        )
    data = res.json() or {}
    return {
        "phone": data.get("phone", user.phone),
        "balance_cents": data.get("balance_cents", 0),
        "currency_code": data.get("currency_code", settings.DEFAULT_CURRENCY if hasattr(settings, "DEFAULT_CURRENCY") else "SYP"),
        "wallet_id": data.get("wallet_id"),
    }
