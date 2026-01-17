"""Сборка индекса (минимальный каркас)."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pgvector index")
    parser.add_argument("--rebuild", action="store_true")
    parser.parse_args()
    raise NotImplementedError("build_index is not implemented yet")


if __name__ == "__main__":
    main()
