"""Совместимый раннер клиента (вызывает legacy main)."""

from __future__ import annotations

import main as legacy_main


def run() -> None:
    legacy_main.main()

