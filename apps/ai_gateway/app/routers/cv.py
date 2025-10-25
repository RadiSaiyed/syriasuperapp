from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
import re


router = APIRouter(prefix="/v1/cv", tags=["cv"])


class CVIn(BaseModel):
    text: str


class CVOut(BaseModel):
    name: str | None
    email: str | None
    phone: str | None
    skills: list[str]


@router.post("/parse", response_model=CVOut)
def parse_cv(payload: CVIn):
    txt = payload.text or ""
    name = None
    m = re.search(r"(?m)^(?:Name|Full Name)\s*[:\-]?\s*(.+)$", txt)
    if m:
        name = m.group(1).strip()
    if not name:
        # naive first line heuristic
        first = txt.strip().splitlines()[0:1]
        if first:
            name = first[0].strip()[:128]
    email = None
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", txt)
    if m:
        email = m.group(0)
    phone = None
    m = re.search(r"(?:\+?\d[\s-]?){7,15}", txt)
    if m:
        phone = re.sub(r"[^+\d]", "", m.group(0))
    # naive skills list from bullet lines
    skills = []
    for line in txt.splitlines():
        if any(line.strip().startswith(p) for p in ("- ", "•", "* ")):
            token = line.strip("-*• \t").strip()
            if 2 <= len(token) <= 40:
                skills.append(token)
    return CVOut(name=name, email=email, phone=phone, skills=skills[:20])

