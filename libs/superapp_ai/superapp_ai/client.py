from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional
import os
import httpx


@dataclass
class AISettings:
    base_url: str
    api_key: str = ""
    timeout: float = 5.0

    @classmethod
    def from_env(cls) -> "AISettings":
        return cls(
            base_url=os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099"),
            api_key=os.getenv("AI_GATEWAY_API_KEY", ""),
            timeout=float(os.getenv("AI_GATEWAY_TIMEOUT", "5.0")),
        )


class AIGatewayClient:
    def __init__(self, settings: Optional[AISettings] = None):
        self.settings = settings or AISettings.from_env()
        headers = {"authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}
        self._client = httpx.Client(base_url=self.settings.base_url, headers=headers, timeout=self.settings.timeout)

    def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            r = self._client.post("/v1/embed", json={"texts": texts})
            r.raise_for_status()
            data = r.json()
            return data.get("embeddings", [])
        except Exception:
            # Local fallback: trivial per-text scalar embedding
            return [[float(len(t))] for t in texts]

    def rank(self, query: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            r = self._client.post("/v1/rank", json={"query": query, "items": items})
            r.raise_for_status()
            data = r.json()
            return data.get("scores", [])
        except Exception:
            # Fallback: naive length-based score
            return [{"id": it.get("id"), "score": float(len(query) / (len(it.get("text", "")) + 1))} for it in items]

    def chat(self, messages: list[dict[str, str]], tools: Optional[list[dict]] = None) -> dict[str, Any]:
        try:
            r = self._client.post("/v1/chat", json={"messages": messages, "tools": tools or []})
            r.raise_for_status()
            return r.json()
        except Exception:
            user_last = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
            return {"role": "assistant", "content": f"(local) {user_last[:200]}", "tool_calls": []}

    def moderate(self, text: str) -> dict[str, Any]:
        try:
            r = self._client.post("/v1/moderate", json={"text": text})
            r.raise_for_status()
            return r.json()
        except Exception:
            lowered = (text or "").lower()
            flagged = any(k in lowered for k in ("scam", "fraud"))
            return {"flagged": flagged, "labels": ["fraud"] if flagged else []}

