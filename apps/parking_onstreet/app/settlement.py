import httpx
from fastapi import HTTPException
from .config import settings


async def settle_with_payments(*, from_phone: str, operator_phone: str, fee_phone: str, net_cents: int, fee_cents: int) -> None:
    base = settings.PAYMENTS_BASE_URL.rstrip('/')
    headers = {"X-Internal-Secret": settings.PAYMENTS_INTERNAL_SECRET}
    async with httpx.AsyncClient(timeout=10) as cli:
        # Transfer net to operator
        if net_cents and net_cents > 0:
            r = await cli.post(
                f"{base}/internal/transfer",
                headers=headers,
                json={"from_phone": from_phone, "to_phone": operator_phone, "amount_cents": int(net_cents)},
            )
            if r.status_code >= 400:
                raise HTTPException(status_code=500, detail=f"settlement_net_failed: {r.text}")
        # Transfer fee to platform
        if fee_cents and fee_cents > 0:
            r = await cli.post(
                f"{base}/internal/transfer",
                headers=headers,
                json={"from_phone": from_phone, "to_phone": fee_phone, "amount_cents": int(fee_cents)},
            )
            if r.status_code >= 400:
                raise HTTPException(status_code=500, detail=f"settlement_fee_failed: {r.text}")

