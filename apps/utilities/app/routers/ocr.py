from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..auth import get_current_user, get_db
from ..models import User
import httpx
import os


router = APIRouter(prefix="/ocr", tags=["ocr"])


class InvoiceOCRIn(BaseModel):
    image_url: str | None = None
    text_hint: str | None = None


class FieldOut(BaseModel):
    key: str
    value: str


class InvoiceOCROut(BaseModel):
    text: str
    fields: list[FieldOut]


@router.post("/invoice", response_model=InvoiceOCROut)
def invoice_ocr(payload: InvoiceOCRIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = {"image_url": payload.image_url, "text_hint": payload.text_hint}
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    try:
        with httpx.Client(base_url=base) as client:
            r = client.post("/v1/ocr", json=body)
            r.raise_for_status()
            data = r.json()
            fields = [FieldOut(key=str(f.get("key")), value=str(f.get("value"))) for f in data.get("fields", [])]
            return InvoiceOCROut(text=str(data.get("text", "")), fields=fields)
    except Exception:
        return InvoiceOCROut(text=payload.text_hint or "", fields=[])
