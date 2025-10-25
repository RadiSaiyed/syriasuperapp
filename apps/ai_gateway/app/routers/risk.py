from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/v1", tags=["risk"])


class RiskFeatures(BaseModel):
    user_id: Optional[str] = None
    signals: Dict[str, float] = {}  # e.g., {"promo_abuse": 0.2, "chargeback_rate": 0.1}
    flags: List[str] = []  # e.g., ["new_device", "vpn", "many_cancellations"]
    recency_days: Optional[int] = None
    kyc_level: Optional[int] = None


class RiskOut(BaseModel):
    score: float  # 0.0 (low) .. 1.0 (high)
    reasons: List[str]
    recommended: List[str]  # e.g., ["step_up_auth", "block_promos"]


@router.post("/risk", response_model=RiskOut)
def compute_risk(payload: RiskFeatures):
    score = 0.0
    reasons: list[str] = []
    rec = set()

    if payload.recency_days is not None and payload.recency_days < 7:
        score += 0.1
        reasons.append("new_user")
    if payload.kyc_level is not None and payload.kyc_level < 1:
        score += 0.15
        reasons.append("low_kyc")
    for k, v in (payload.signals or {}).items():
        w = min(max(v, 0.0), 1.0)
        score += 0.25 * w
        if w > 0.3:
            reasons.append(k)
    if payload.flags:
        score += 0.05 * len(payload.flags)
        reasons.extend(payload.flags)

    # clamp
    score = max(0.0, min(1.0, score))

    if score > 0.7:
        rec.update(["block_promos", "manual_review"])
    elif score > 0.4:
        rec.update(["step_up_auth", "cap_limits"])
    else:
        rec.update(["allow"])

    return RiskOut(score=round(score, 3), reasons=list(dict.fromkeys(reasons)), recommended=sorted(rec))

