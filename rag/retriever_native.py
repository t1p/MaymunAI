"""Нативный ретривер (минимальная реализация)."""

from __future__ import annotations

from typing import List, Dict, Any

from db import pg_native
from retrieval import rerank_items


def retrieve(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    items = pg_native.fetch_documents(limit=max(top_k, 10))
    # Используем текущий пайплайн реранжирования как базовый слой.
    return rerank_items(query, items, top_k=top_k)
