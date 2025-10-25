from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..auth import get_current_user, get_db
from ..models import User
from pydantic import BaseModel
import os


router = APIRouter(prefix="/help", tags=["help"])


class HelpItem(BaseModel):
    id: str
    text: str
    score: float


class HelpSearchOut(BaseModel):
    items: list[HelpItem]


@router.get("/search", response_model=HelpSearchOut)
def help_search(q: str = Query(..., min_length=2, max_length=300), limit: int = Query(5, ge=1, le=20), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # search in 'help' collection via AI Gateway RAG store
    import httpx
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    try:
        with httpx.Client(base_url=base) as client:
            r = client.post("/v1/store/search", json={"collection": "help", "query": q, "k": limit})
            r.raise_for_status()
            data = r.json()
            items = data.get("items", [])
            out = [HelpItem(id=str(it.get("id")), text=str(it.get("text")), score=float(it.get("score", 0))) for it in items]
            return HelpSearchOut(items=out)
    except Exception:
        # graceful fallback
        return HelpSearchOut(items=[])
