from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..providers import BaseProvider, build_provider
from ..config import settings
from ..rag_store import RAGItem, store


router = APIRouter(prefix="/v1/store", tags=["rag"])


def get_provider() -> BaseProvider:
    return build_provider(settings.PROVIDER, settings.PROVIDER_BASE_URL, settings.PROVIDER_API_KEY)


class UpsertItem(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] | None = None


class UpsertRequest(BaseModel):
    collection: str
    items: List[UpsertItem]


class UpsertResponse(BaseModel):
    upserted: int


@router.post("/upsert", response_model=UpsertResponse)
def upsert(payload: UpsertRequest, provider: BaseProvider = Depends(get_provider)):
    embs = provider.embed([it.text for it in payload.items])
    rag_items = [
        RAGItem(id=it.id, text=it.text, metadata=it.metadata or {}, embedding=e)
        for it, e in zip(payload.items, embs)
    ]
    n = store.upsert(payload.collection, rag_items)
    return UpsertResponse(upserted=n)


class SearchRequest(BaseModel):
    collection: str
    query: str
    k: int = 5


class ScoredItem(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = {}
    score: float


class SearchResponse(BaseModel):
    items: List[ScoredItem]


@router.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, provider: BaseProvider = Depends(get_provider)):
    q = provider.embed([payload.query])[0]
    results = store.search(payload.collection, q, k=payload.k)
    return SearchResponse(items=[ScoredItem(id=it.id, text=it.text, metadata=it.metadata, score=score) for it, score in results])

