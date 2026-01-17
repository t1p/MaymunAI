"""Сборка контекста и guardrails (минимальная реализация)."""

from __future__ import annotations

from typing import List, Dict, Any


def compose_context(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for item in items:
        text = item.get("text") or ""
        if not text.strip():
            continue
        cleaned.append(item)
    return cleaned
