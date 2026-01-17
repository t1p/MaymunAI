"""Настройка логирования (минимальная реализация)."""

from __future__ import annotations

import logging
from typing import Dict
import json
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", fmt: str = "json", file: str | None = None, module_levels: Dict[str, str] | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if file:
        handlers.append(logging.FileHandler(file))
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=handlers)
    if fmt == "json":
        formatter = JsonFormatter()
        for handler in handlers:
            handler.setFormatter(formatter)
    if module_levels:
        for module, mod_level in module_levels.items():
            logging.getLogger(module).setLevel(getattr(logging, mod_level.upper(), logging.INFO))
