from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
import httpx

from ..config import settings
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/v1", tags=["digest"])


class DigestItem(BaseModel):
    title: str
    detail: Optional[str] = None
    link: Optional[str] = None


class DigestRequest(BaseModel):
    user_id: str
    items: List[DigestItem] = []


class DigestResponse(BaseModel):
    delivered: bool


@router.post("/digest", response_model=DigestResponse)
def send_digest(payload: DigestRequest, request: Request, authorization: str | None = Header(default=None, alias="Authorization")):
    # Build a simple textual digest
    lines = ["Dein Wochenüberblick:"]
    for i, it in enumerate(payload.items or [], start=1):
        line = f"{i}. {it.title}"
        if it.detail:
            line += f" — {it.detail}"
        lines.append(line)
    text = "\n".join(lines)

    body = {"user_id": payload.user_id, "text": text}
    headers = sign_internal_request_headers(body, settings.INTERNAL_API_SECRET, request.headers.get("X-Request-ID", ""))
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(
                f"{settings.CHAT_BASE_URL}/internal/tools/system_notify",
                headers={**headers, **({"Authorization": authorization} if authorization else {})},
                json=body,
            )
            if r.status_code >= 400:
                raise HTTPException(status_code=r.status_code, detail=r.text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Chat delivery failed: {e}")
    return DigestResponse(delivered=True)
