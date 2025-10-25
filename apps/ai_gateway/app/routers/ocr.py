from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import base64
import re


router = APIRouter(prefix="/v1", tags=["ocr"])


class OCRRequest(BaseModel):
    image_url: Optional[str] = None
    image_b64: Optional[str] = None
    text_hint: Optional[str] = None


class OCRField(BaseModel):
    key: str
    value: str


class OCRResponse(BaseModel):
    text: str
    fields: List[OCRField]


def _extract_fields(text: str) -> List[OCRField]:
    out: list[OCRField] = []
    # Amounts
    m = re.search(r"(?i)(total|amount|sum)\s*[:=]?\s*([0-9]+[\.,][0-9]{2}|[0-9]+)", text)
    if m:
        out.append(OCRField(key="amount", value=m.group(2).replace(",", ".")))
    # Invoice number
    m = re.search(r"(?i)(invoice|bill|ref|no\.?|number)\s*[:#-]?\s*([A-Za-z0-9\-_/]{4,})", text)
    if m:
        out.append(OCRField(key="invoice_number", value=m.group(2)))
    # Dates (YYYY-MM-DD or DD/MM/YYYY)
    m = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", text)
    if m:
        out.append(OCRField(key="date", value=m.group(1)))
    # Due date keywords
    m = re.search(r"(?i)(due\s*date|pay\s*by|fällig)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", text)
    if m:
        out.append(OCRField(key="due_date", value=m.group(2)))
    return out


@router.post("/ocr", response_model=OCRResponse)
def ocr(payload: OCRRequest):
    # Minimal OCR stub: prefers text_hint. If image is provided without text_hint, return 400 for now.
    text = (payload.text_hint or "").strip()
    if not text:
        # Accept base64 string but not actually OCR it; avoid heavy dependencies in MVP.
        if payload.image_url or payload.image_b64:
            raise HTTPException(status_code=400, detail="OCR image processing not enabled; provide text_hint for MVP")
        raise HTTPException(status_code=400, detail="Provide text_hint or image")
    fields = _extract_fields(text)
    return OCRResponse(text=text, fields=fields)

