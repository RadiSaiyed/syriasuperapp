from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import threading
import numpy as np


@dataclass
class RAGItem:
    id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class InMemoryRAGStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cols: Dict[str, Dict[str, RAGItem]] = {}

    def upsert(self, collection: str, items: List[RAGItem]) -> int:
        with self._lock:
            col = self._cols.setdefault(collection, {})
            for it in items:
                col[it.id] = it
            return len(items)

    def search(self, collection: str, query_emb: List[float], k: int = 5) -> List[tuple[RAGItem, float]]:
        with self._lock:
            col = self._cols.get(collection) or {}
            if not col:
                return []
            q = np.array(query_emb, dtype=np.float32)
            qn = np.linalg.norm(q) or 1.0
            scored: list[tuple[RAGItem, float]] = []
            for it in col.values():
                v = np.array(it.embedding, dtype=np.float32)
                denom = qn * (np.linalg.norm(v) or 1.0)
                score = float(np.dot(q, v) / denom)
                scored.append((it, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[: max(1, min(100, k))]


store = InMemoryRAGStore()

