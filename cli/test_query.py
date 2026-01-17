"""Тестовый запрос (минимальный каркас)."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Test RAG query")
    parser.add_argument("--q", required=True, help="Query text")
    parser.add_argument("--top_k", type=int, default=5)
    parser.parse_args()
    raise NotImplementedError("test_query is not implemented yet")


if __name__ == "__main__":
    main()
