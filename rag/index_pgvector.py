"""Индексация pgvector (минимальная реализация через legacy db)."""

from __future__ import annotations

from typing import Iterable

import db as legacy_db
from rag.embed_openai import embed_text


def build_index(texts: Iterable[str]) -> list[list[float]]:
    legacy_db.create_embeddings_table()
    embeddings = [embed_text(text) for text in texts]
    return embeddings
