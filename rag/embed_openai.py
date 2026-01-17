"""Эмбеддинги OpenAI (минимальная реализация)."""

from __future__ import annotations

from typing import List

from openai import OpenAI

from config import MODELS


def embed_text(text: str) -> List[float]:
    client = OpenAI()
    response = client.embeddings.create(model=MODELS["embedding"]["name"], input=text)
    return response.data[0].embedding
