#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.synthesis import synthesize_execution_plan  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate job artifacts and synthesize full-manifest benchmark outputs."
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--table", type=Path)
    parser.add_argument("--validator", type=Path)
    parser.add_argument("--require-all-usable", action="store_true")
    parser.add_argument("--require-slurm-clean", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    synthesize_execution_plan(
        args.plan,
        args.output_dir,
        table_path=args.table,
        validator_path=args.validator,
        require_all_usable=args.require_all_usable,
        require_slurm_clean=args.require_slurm_clean,
    )
    print(f"synthesis={args.output_dir / 'synthesis.json'}")


if __name__ == "__main__":
    main()
