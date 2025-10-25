from __future__ import annotations

from typing import Any, Dict, Tuple
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from prometheus_client import Counter
import httpx

from ..config import settings
from ..tools import TOOLS
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/v1/tools", tags=["tools"])

TOOL_EXEC = Counter("ai_tools_executed_total", "AI tools executed", ["tool", "result"])  # result: success|error


class ExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any]
    user_id: str


class ExecuteResponse(BaseModel):
    detail: str = "ok"
    result: Dict[str, Any] | None = None


def dispatch_tool(name: str, args: Dict[str, Any], user_id: str, request: Request, authorization: str | None) -> Dict[str, Any]:
    name = (name or "").strip()
    if name not in TOOLS:
        raise HTTPException(status_code=400, detail="Unknown tool")

    payload = ExecuteRequest(tool=name, args=args, user_id=user_id)

    # Currently supported: pay_bill, start_parking_session, create_car_listing
    if name == "pay_bill":
        bill_id = args.get("bill_id")
        if not bill_id:
            raise HTTPException(status_code=400, detail="Missing bill_id")
        body = {"user_id": user_id, "bill_id": str(bill_id)}
        headers = sign_internal_request_headers(body, settings.INTERNAL_API_SECRET, request.headers.get("X-Request-ID", ""))
        headers_extra = {"X-Idempotency-Key": f"ai-pay-bill-{user_id}-{bill_id}"}
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.UTILITIES_BASE_URL}/internal/tools/pay_bill",
                    headers={**headers, **headers_extra, **({"Authorization": authorization} if authorization else {})},
                    json=body,
                )
                if r.status_code >= 400:
                    TOOL_EXEC.labels(name, "error").inc()
                    raise HTTPException(status_code=r.status_code, detail=r.text)
                TOOL_EXEC.labels(name, "success").inc()
                return r.json()
        except HTTPException:
            raise
        except Exception as e:
            TOOL_EXEC.labels(name, "error").inc()
            raise HTTPException(status_code=502, detail=f"Downstream error: {e}")

    if name == "start_parking_session":
        zone_id = args.get("zone_id")
        plate = args.get("plate")
        minutes = args.get("minutes")
        if not zone_id or not plate:
            raise HTTPException(status_code=400, detail="Missing zone_id or plate")
        body = {"user_id": user_id, "zone_id": str(zone_id), "plate": str(plate), "minutes": int(minutes) if minutes else None}
        headers = sign_internal_request_headers(body, settings.INTERNAL_API_SECRET, request.headers.get("X-Request-ID", ""))
        headers_extra = {"X-Idempotency-Key": f"ai-park-start-{user_id}-{zone_id}-{plate}"}
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PARKING_ONSTREET_BASE_URL}/internal/tools/start_parking",
                    headers={**headers, **headers_extra, **({"Authorization": authorization} if authorization else {})},
                    json=body,
                )
                if r.status_code >= 400:
                    TOOL_EXEC.labels(name, "error").inc()
                    raise HTTPException(status_code=r.status_code, detail=r.text)
                TOOL_EXEC.labels(name, "success").inc()
                return r.json()
        except HTTPException:
            raise
        except Exception as e:
            TOOL_EXEC.labels(name, "error").inc()
            raise HTTPException(status_code=502, detail=f"Downstream error: {e}")

    if name == "create_car_listing":
        title = args.get("title")
        make = args.get("make")
        model = args.get("model")
        year = args.get("year")
        price_cents = args.get("price_cents")
        if not all([title, make, model, year, price_cents]):
            raise HTTPException(status_code=400, detail="Missing listing fields")
        body = {
            "user_id": user_id,
            "title": str(title),
            "make": str(make),
            "model": str(model),
            "year": int(year),
            "price_cents": int(price_cents),
        }
        headers = sign_internal_request_headers(body, settings.INTERNAL_API_SECRET, request.headers.get("X-Request-ID", ""))
        headers_extra = {"X-Idempotency-Key": f"ai-carmarket-create-{user_id}-{title[:20]}-{make}-{model}-{year}-{price_cents}"}
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.CARMARKET_BASE_URL}/internal/tools/create_listing",
                    headers={**headers, **headers_extra, **({"Authorization": authorization} if authorization else {})},
                    json=body,
                )
                if r.status_code >= 400:
                    TOOL_EXEC.labels(name, "error").inc()
                    raise HTTPException(status_code=r.status_code, detail=r.text)
                TOOL_EXEC.labels(name, "success").inc()
                return r.json()
        except HTTPException:
            raise
        except Exception as e:
            TOOL_EXEC.labels(name, "error").inc()
            raise HTTPException(status_code=502, detail=f"Downstream error: {e}")

    raise HTTPException(status_code=400, detail="Tool not implemented")


@router.post("/execute", response_model=ExecuteResponse)
def execute_tool(payload: ExecuteRequest, request: Request, authorization: str | None = Header(default=None, alias="Authorization")):
    result = dispatch_tool(payload.tool, payload.args, payload.user_id, request, authorization)
    return ExecuteResponse(result=result)
