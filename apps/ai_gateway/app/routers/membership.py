from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
import os


router = APIRouter(prefix="/v1/membership", tags=["membership"])


class MemberStatus(BaseModel):
    user_id: str
    tier: str  # none|basic|prime
    benefits: List[str] = []  # e.g., ["fee_discount_10", "priority_support"]


@router.get("/status", response_model=MemberStatus)
def status(user_id: str, phone: Optional[str] = None):
    # MVP: decide via env allowlist of phones or default
    allow = set([p.strip() for p in (os.getenv("SUPERPASS_PHONES", "").split(",")) if p.strip()])
    tier = "prime" if (phone and phone in allow) else "none"
    benefits = ["priority_support", "digest", "risk_protection"]
    if tier == "prime":
        benefits += ["fee_discount_10", "parking_discount_5"]
    return MemberStatus(user_id=user_id, tier=tier, benefits=benefits)

