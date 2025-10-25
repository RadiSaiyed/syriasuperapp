from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/v1/estimate", tags=["pricing"])


class CarIn(BaseModel):
    title: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    city: str | None = None


class PriceOut(BaseModel):
    estimate_cents: int
    conf: float
    basis: dict


@router.post("/car", response_model=PriceOut)
def estimate_car(payload: CarIn):
    # Simple heuristic: base by year, mileage penalty, city modifier (MVP, deterministic)
    base = 8_000_000  # default
    if payload.year:
        age = max(0, 2025 - int(payload.year))
        base = max(1_000_000, 20_000_000 - age * 800_000)
    mileage = payload.mileage_km or 120_000
    penalty = int(min(0.5, (mileage / 200_000.0)) * base)
    city_mod = 1.0
    if payload.city:
        city = payload.city.lower()
        if any(k in city for k in ("damascus", "دمشق")):
            city_mod = 1.05
        elif any(k in city for k in ("aleppo", "حلب")):
            city_mod = 0.98
    est = int(max(500_000, (base - penalty) * city_mod))
    conf = 0.6
    return PriceOut(estimate_cents=est, conf=conf, basis={"base": base, "penalty": penalty, "city_mod": city_mod})

