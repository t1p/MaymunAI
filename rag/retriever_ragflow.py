"""RAGFlow ретривер (базовая реализация через REST API)."""

from __future__ import annotations


from typing import Any, Dict, List

import httpx

from core.settings import load_config


def retrieve(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    config = load_config()
    base_url = config.ragflow.base_url.rstrip("/")
    api_key = config.ragflow.api_key
    index = config.ragflow.index

    if not api_key or not index:
        raise ValueError("RAGFLOW_API_KEY or ragflow.index is not configured")

    payload = {
        "query": query,
        "top_k": top_k,
        "index": index,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    with httpx.Client(timeout=30) as client:
        response = client.post(f"{base_url}/api/v1/query", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    results: List[Dict[str, Any]] = []
    for item in data.get("data", []):
        results.append(
            {
                "text": item.get("content") or item.get("text") or "",
                "score": item.get("score", 0.0),
                "citation": item.get("citation") or {},
                "metadata": item,
            }
        )

    return results

def retrieve(query: str, top_k: int = 5):
    raise NotImplementedError("RAGFlow retriever is not implemented yet")
