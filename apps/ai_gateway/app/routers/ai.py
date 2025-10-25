from __future__ import annotations

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
import numpy as np

from ..providers import BaseProvider, build_provider
from ..tools import infer_tool_calls
from .tools import dispatch_tool
from ..config import settings


router = APIRouter(prefix="/v1", tags=["ai"])


def get_provider() -> BaseProvider:
    return build_provider(settings.PROVIDER, settings.PROVIDER_BASE_URL, settings.PROVIDER_API_KEY)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    tools: Optional[list[dict[str, Any]]] = Field(default=None, description="Optional tool definitions")
    allow_tools: bool = Field(default=True, description="Allow gateway to suggest tool calls")
    confirm: bool = Field(default=False, description="If true and selected_tool provided, executes it")
    selected_tool: Optional[dict[str, Any]] = Field(default=None, description="{ tool: str, args: dict, user_id: str }")


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    tool_calls: list[dict[str, Any]] = []
    executed_tool: Optional[str] = None
    execution_result: Optional[dict[str, Any]] = None


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, provider: BaseProvider = Depends(get_provider), authorization: str | None = Header(default=None, alias="Authorization")):
    res = provider.chat([m.model_dump() for m in payload.messages], tools=payload.tools)
    out = ChatResponse(**{k: v for k, v in res.items() if k in ("role", "content", "tool_calls")})
    if payload.allow_tools:
        # Best-effort light intent detection for tool suggestions
        user_last = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
        calls = infer_tool_calls(user_last)
        if calls:
            out.tool_calls = calls
            if not out.content:
                out.content = "I can perform actions. Please confirm."
    if payload.confirm and payload.selected_tool and isinstance(payload.selected_tool, dict):
        try:
            tool_name = str(payload.selected_tool.get("tool"))
            args = payload.selected_tool.get("args") or {}
            user_id = str(payload.selected_tool.get("user_id"))
            result = dispatch_tool(tool_name, args, user_id, request, authorization)
            out.executed_tool = tool_name
            out.execution_result = result
            if not out.content:
                out.content = "Action executed successfully."
        except HTTPException as e:
            # surface error as content
            out.executed_tool = str(payload.selected_tool.get("tool"))
            out.content = f"Execution error: {e.detail}"
    return out


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]


@router.post("/embed", response_model=EmbedResponse)
def embed(payload: EmbedRequest, provider: BaseProvider = Depends(get_provider)):
    embs = provider.embed(payload.texts)
    return EmbedResponse(embeddings=embs)


class RankItem(BaseModel):
    id: str
    text: str


class RankRequest(BaseModel):
    query: str
    items: List[RankItem]


class RankScore(BaseModel):
    id: str
    score: float


class RankResponse(BaseModel):
    scores: List[RankScore]


@router.post("/rank", response_model=RankResponse)
def rank(payload: RankRequest, provider: BaseProvider = Depends(get_provider)):
    # Inference: embed query and items, then cosine similarity
    embs = provider.embed([payload.query] + [it.text for it in payload.items])
    q = np.array(embs[0], dtype=np.float32)
    scores: list[RankScore] = []
    for it, e in zip(payload.items, embs[1:]):
        v = np.array(e, dtype=np.float32)
        denom = (np.linalg.norm(q) or 1.0) * (np.linalg.norm(v) or 1.0)
        sim = float(np.dot(q, v) / denom)
        scores.append(RankScore(id=it.id, score=sim))
    scores.sort(key=lambda x: x.score, reverse=True)
    return RankResponse(scores=scores)


class ModerateRequest(BaseModel):
    text: str


class ModerateResponse(BaseModel):
    flagged: bool
    labels: list[str] = []


@router.post("/moderate", response_model=ModerateResponse)
def moderate(payload: ModerateRequest, provider: BaseProvider = Depends(get_provider)):
    res = provider.moderate(payload.text)
    if not isinstance(res, dict) or "flagged" not in res:
        raise HTTPException(status_code=500, detail="Provider response invalid")
    return ModerateResponse(flagged=bool(res.get("flagged")), labels=[str(x) for x in res.get("labels", [])])
