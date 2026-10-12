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
from benchmark.qasper_quality_focus import (  # noqa: E402
    QASPER_QUALITY_FOCUS_SOURCE_RUN_SHA,
    build_qasper_quality_focus_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the current-run-derived QASPER quality 6x3 manifest."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-run-sha",
        default=QASPER_QUALITY_FOCUS_SOURCE_RUN_SHA,
    )
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("source manifest must contain one JSON object")
    manifest = build_qasper_quality_focus_manifest(
        source,
        source_run_sha=args.source_run_sha,
        source_artifact=str(args.source.resolve()),
    )
    atomic_write_json(args.output, manifest)
    quality_focus = manifest["metadata"]["quality_focus"]
    print(
        f"manifest={args.output.resolve()} examples={len(manifest['examples'])} "
        f"routes={quality_focus['route_count']} "
        f"expected_predictions={quality_focus['expected_prediction_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
