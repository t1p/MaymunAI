"""Runtime loader for Project Packs.

Pack files are treated as source of truth and can be updated without
core code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


PACKS_DIR = Path(__file__).resolve().parent
PACK_INDEX_PATH = PACKS_DIR / "index.yaml"


@dataclass(frozen=True)
class PackContext:
    """Routing context for pack resolution."""

    chat_id: Optional[str] = None
    group: Optional[str] = None
    topic: Optional[str] = None


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Pack config not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Pack config must be a mapping: {path}")
    return payload


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Pack text file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_pack_index(index_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load global pack index file."""

    target = index_path or PACK_INDEX_PATH
    return _read_yaml(target)


def resolve_pack_for_context(
    context: Optional[Dict[str, Any]] = None,
    *,
    index_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Resolve pack by chat/group/topic context.

    Resolution order:
    1) by_chat_id
    2) by_topic
    3) by_group
    4) default_pack
    """

    ctx = context or {}
    index_payload = index_data or load_pack_index()
    routing = index_payload.get("routing", {})

    chat_id = ctx.get("chat_id")
    topic = ctx.get("topic")
    group = ctx.get("group")

    by_chat_id = routing.get("by_chat_id", {})
    by_topic = routing.get("by_topic", {})
    by_group = routing.get("by_group", {})

    if chat_id is not None and str(chat_id) in by_chat_id:
        return by_chat_id[str(chat_id)]
    if topic is not None and str(topic) in by_topic:
        return by_topic[str(topic)]
    if group is not None and str(group) in by_group:
        return by_group[str(group)]

    default_pack = index_payload.get("default_pack")
    if not default_pack:
        raise ValueError("default_pack is not configured in packs/index.yaml")
    return str(default_pack)


def _resolve_pack_path(pack_name: str, *, index_data: Optional[Dict[str, Any]] = None) -> Path:
    index_payload = index_data or load_pack_index()
    packs = index_payload.get("packs", [])

    for entry in packs:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == pack_name:
            rel_path = entry.get("path", pack_name)
            return PACKS_DIR / str(rel_path)

    return PACKS_DIR / pack_name


def get_system_prompt_for_pack(
    pack_name: str,
    *,
    index_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Return system prompt text for pack."""

    pack_dir = _resolve_pack_path(pack_name, index_data=index_data)
    return _read_text(pack_dir / "prompts" / "system.md")


def get_pack_model_preset(
    pack_name: str,
    *,
    index_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return model preset for pack."""

    pack_dir = _resolve_pack_path(pack_name, index_data=index_data)
    return _read_yaml(pack_dir / "presets" / "model.yaml")


def get_guardrails_for_pack(
    pack_name: str,
    *,
    index_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return guardrails config for pack."""

    pack_dir = _resolve_pack_path(pack_name, index_data=index_data)
    return _read_yaml(pack_dir / "guardrails.yaml")

