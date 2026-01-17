"""FastGPT ретривер (базовая реализация через REST API)."""

from __future__ import annotations


from typing import Any, Dict, List

import httpx

from core.settings import load_config


def retrieve(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    config = load_config()
    base_url = config.fastgpt.base_url.rstrip("/")
    api_key = config.fastgpt.api_key
    dataset_id = config.fastgpt.dataset_id

    if not api_key or not dataset_id:
        raise ValueError("FASTGPT_API_KEY or FASTGPT_DATASET_ID is not configured")

    payload = {
        "datasetId": dataset_id,
        "q": query,
        "limit": top_k,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    with httpx.Client(timeout=30) as client:
        response = client.post(f"{base_url}/api/v1/search", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    results: List[Dict[str, Any]] = []
    for item in data.get("data", []):
        results.append(
            {
                "text": item.get("content") or item.get("text") or "",
                "score": item.get("score", 0.0),
                "citation": item.get("source", {}),
                "metadata": item,
            }
        )

    return results
