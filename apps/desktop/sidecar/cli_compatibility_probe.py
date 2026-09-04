from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def validate_cli_records(
    payload: Any,
    *,
    expected_name: str | None = None,
    expect_empty: bool = False,
) -> list[str]:
    if not isinstance(payload, list) or not all(
        isinstance(record, dict) for record in payload
    ):
        raise ValueError("MARA docqa files did not return a record list")

    names = sorted(Path(str(record.get("name", ""))).name for record in payload)
    if expect_empty and names:
        raise ValueError("MARA docqa files still reports indexed records")
    if expected_name and expected_name not in names:
        raise ValueError(f"Expected indexed record is missing: {expected_name}")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CLI/Desktop data compatibility without retaining paths."
    )
    parser.add_argument("--phase", required=True)
    parser.add_argument("--expect-name")
    parser.add_argument("--expect-empty", action="store_true")
    parser.add_argument("--summary-file", required=True, type=Path)
    arguments = parser.parse_args()

    names = validate_cli_records(
        json.load(sys.stdin),
        expected_name=arguments.expect_name,
        expect_empty=arguments.expect_empty,
    )
    arguments.summary_file.write_text(
        "\n".join(
            (
                f"phase={arguments.phase}",
                f"record_count={len(names)}",
                f"record_names={','.join(names)}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
