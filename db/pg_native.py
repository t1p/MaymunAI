"""Нативный доступ к Postgres (адаптер к существующему db.py)."""

from __future__ import annotations

from typing import Any, Dict, List

import db as legacy_db


def list_tables() -> List[str]:
    return legacy_db.get_tables()


def fetch_documents(limit: int = 10) -> List[Dict[str, Any]]:
    return legacy_db.get_items_sample(sample_size=limit)


def fetch_by_text(text: str, context: int = 2) -> List[Dict[str, Any]]:
    return legacy_db.search_text(text, context=context)


def get_schema_snapshot() -> Dict[str, Any]:
    tables = legacy_db.get_tables()
    return {table: legacy_db.get_table_info(table) for table in tables}
