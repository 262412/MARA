from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def normalize_semantic_evaluator(value: str) -> str:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    if lowered in {"", "off", "none"}:
        return "off"
    if lowered in {
        "on",
        "true",
        "1",
        "local",
        "local_qwen3_8b",
        "builtin:local_qwen3_8b",
    }:
        return "local_qwen3_8b"

    module_name, separator, attribute = normalized.rpartition(".")
    if not separator:
        raise ValueError(
            "semantic evaluator must be off, local_qwen3_8b, or a Python path"
        )
    candidate = getattr(importlib.import_module(module_name), attribute)
    if not callable(candidate):
        raise TypeError(f"semantic evaluator is not callable: {normalized}")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        print(normalize_semantic_evaluator(args.backend))
    except (AttributeError, ImportError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
