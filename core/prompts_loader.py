"""Загрузка системных и профильных промптов."""

from __future__ import annotations

from typing import Dict
from pathlib import Path


def load_prompts(paths: list[str]) -> Dict[str, str]:
    prompts: Dict[str, str] = {}
    for base in paths:
        base_path = Path(base)
        if not base_path.exists():
            continue
        for file_path in base_path.rglob("*.md"):
            prompts[str(file_path)] = file_path.read_text(encoding="utf-8")
    return prompts
