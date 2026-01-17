"""Ингест документов (минимальный каркас)."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into index")
    parser.add_argument("--source", required=True, help="Path or SQL source")
    parser.add_argument("--chunk", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=200)
    parser.parse_args()
    raise NotImplementedError("ingest_docs is not implemented yet")


if __name__ == "__main__":
    main()
