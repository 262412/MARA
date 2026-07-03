from __future__ import annotations

import argparse
import json


def add_format_smoke_commands(subparsers: argparse._SubParsersAction) -> None:
    fixtures_parser = subparsers.add_parser(
        "build-format-smoke-fixtures",
        help="Build tiny PDF/Word/PPTX/Excel/CSV/Markdown/text smoke fixtures",
    )
    fixtures_parser.add_argument("--source-dir", required=True)
    fixtures_parser.add_argument("--manifest", required=True)

    smoke_parser = subparsers.add_parser(
        "run-format-smoke",
        help="Run deterministic indexing/query smoke checks for a format manifest",
    )
    smoke_parser.add_argument("--manifest", required=True)
    smoke_parser.add_argument("--output")
    smoke_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 when any format smoke check fails.",
    )


def handle_format_smoke_command(args: argparse.Namespace) -> int | None:
    if args.command == "build-format-smoke-fixtures":
        from .format_smoke_harness import build_format_smoke_fixtures

        output_path = build_format_smoke_fixtures(args.source_dir, args.manifest)
        print(f"Format smoke manifest written to {output_path}")
        return 0

    if args.command == "run-format-smoke":
        from .format_smoke_harness import (
            run_format_smoke_harness,
            write_format_smoke_report,
        )

        report = run_format_smoke_harness(args.manifest)
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            output_path = write_format_smoke_report(report, args.output)
            print(f"Format smoke report written to {output_path}")
        else:
            print(payload)
        return 2 if args.strict and report["overall_status"] != "pass" else 0

    return None
