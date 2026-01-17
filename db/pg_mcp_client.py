"""MCP-клиент к enhanced-postgres-mcp-server (каркас)."""

from __future__ import annotations


def list_tables() -> list[str]:
    raise NotImplementedError("MCP client is not implemented yet")


def fetch_documents(limit: int = 10):
    raise NotImplementedError("MCP client is not implemented yet")


def fetch_by_text(text: str, context: int = 2):
    raise NotImplementedError("MCP client is not implemented yet")
