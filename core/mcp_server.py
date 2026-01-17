"""MCP-сервер MaymunAI (минимальный каркас)."""

from __future__ import annotations

from typing import Dict, Any, Callable

from db import schema_introspect
from rag import retriever_native


def tool_retrieval(query: str, top_k: int = 5, retriever_mode: str | None = None) -> Dict[str, Any]:
    return {
        "items": retriever_native.retrieve(query, top_k=top_k),
        "mode": retriever_mode or "RAG_NATIVE",
    }


def tool_info_schema() -> Dict[str, Any]:
    return schema_introspect.describe_schema()


TOOLS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "tool.retrieval": tool_retrieval,
    "tool.info.schema": tool_info_schema,
}


def run_mcp_server() -> None:
    raise NotImplementedError("MCP server wiring pending: expose stdio/SSE transport and tool registry")
