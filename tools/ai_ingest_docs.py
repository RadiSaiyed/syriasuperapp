#!/usr/bin/env python3
"""
Ingest markdown docs into the AI Gateway RAG store.

Usage:
  AI_GATEWAY_BASE_URL=http://localhost:8099 python tools/ai_ingest_docs.py
"""
from __future__ import annotations

import os
import glob
import httpx


BASE = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")


def read_docs(root: str = "docs"):
    paths = glob.glob(os.path.join(root, "**", "*.md"), recursive=True)
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
            # Trim overly large files
            if len(text) > 8000:
                text = text[:8000]
            yield p, text
        except Exception:
            continue


def main():
    items = []
    for p, text in read_docs():
        items.append({"id": p, "text": text, "metadata": {"path": p}})
    if not items:
        print("No docs found to ingest.")
        return
    with httpx.Client(base_url=BASE) as client:
        r = client.post("/v1/store/upsert", json={"collection": "help", "items": items})
        r.raise_for_status()
        print("Upserted:", r.json())


if __name__ == "__main__":
    main()

