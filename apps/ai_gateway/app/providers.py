from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional
import hashlib
import numpy as np
import httpx


@dataclass
class ProviderConfig:
    name: str
    base_url: str = ""
    api_key: str = ""


class BaseProvider:
    def embed(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover - interface
        raise NotImplementedError

    def chat(self, messages: List[dict[str, str]], tools: Optional[list[dict]] = None) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def moderate(self, text: str) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class LocalProvider(BaseProvider):
    """Deterministic, dependency-free fallback provider.

    - Embeddings: simple hash-based projections to 256D.
    - Chat: echo with small helpers.
    - Moderate: naive keyword filter.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _hash_to_vec(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat hash to fill dimension and map bytes to [-1, 1]
        arr = np.frombuffer((h * ((self.dim // len(h)) + 1))[: self.dim], dtype=np.uint8).astype(np.float32)
        arr = (arr / 127.5) - 1.0
        # L2 normalize
        norm = np.linalg.norm(arr) or 1.0
        return arr / norm

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vec(t).tolist() for t in texts]

    def chat(self, messages: List[dict[str, str]], tools: Optional[list[dict]] = None) -> dict[str, Any]:
        user_last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return {
            "role": "assistant",
            "content": f"(stub) You said: {user_last[:400]}",
            "tool_calls": [],
        }

    def moderate(self, text: str) -> dict[str, Any]:
        bad = ["scam", "fraud", "hate", "terror", "violence"]
        lowered = text.lower()
        flagged = any(k in lowered for k in bad)
        return {"flagged": bool(flagged), "labels": [k for k in bad if k in lowered]}


class HTTPProvider(BaseProvider):
    """Proxy to external/base URL provider that exposes compatible routes.

    This is intentionally thin to allow swapping for real vendors later.
    """

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.client = httpx.Client(base_url=cfg.base_url, headers={"authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {})

    def embed(self, texts: List[str]) -> List[List[float]]:
        r = self.client.post("/v1/embed", json={"texts": texts})
        r.raise_for_status()
        data = r.json()
        return data.get("embeddings", [])

    def chat(self, messages: List[dict[str, str]], tools: Optional[list[dict]] = None) -> dict[str, Any]:
        r = self.client.post("/v1/chat", json={"messages": messages, "tools": tools or []})
        r.raise_for_status()
        return r.json()

    def moderate(self, text: str) -> dict[str, Any]:
        r = self.client.post("/v1/moderate", json={"text": text})
        r.raise_for_status()
        return r.json()


def build_provider(name: str, base_url: str, api_key: str) -> BaseProvider:
    name = (name or "").strip().lower()
    if name in ("", "local"):
        return LocalProvider()
    return HTTPProvider(ProviderConfig(name=name, base_url=base_url, api_key=api_key))

