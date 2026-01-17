"""Интроспекция схемы БД (минимальная реализация)."""

from __future__ import annotations


from typing import Dict

from db import pg_native


def describe_schema() -> dict:
    schema_snapshot = pg_native.get_schema_snapshot()
    return {
        "tables": schema_snapshot,
    }
