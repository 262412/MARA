#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.artifact_publication import atomic_write_json  # noqa: E402
from benchmark.manifest_subset import build_manifest_subset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a frozen benchmark manifest for exact example IDs."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--example-id", action="append", required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("source manifest must contain one JSON object")
    subset = build_manifest_subset(source, args.example_id)
    atomic_write_json(args.output, subset)
    print(
        f"manifest={args.output.resolve()} examples={len(subset['examples'])} "
        f"documents={len(subset['documents'])} routes={len(subset.get('routes') or [])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
