from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

SHA256_DIGEST = re.compile(r"sha256:([0-9a-f]{64})")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_container_evidence(
    metadata: dict,
    *,
    target: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    digest = metadata.get("containerimage.digest", "")
    match = SHA256_DIGEST.fullmatch(digest)
    if not match:
        raise ValueError("Build metadata has no valid container digest")
    provenance = metadata.get("buildx.build.provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("Build metadata has no BuildKit provenance")

    output_dir.mkdir(parents=True, exist_ok=True)
    statement_path = output_dir / f"{target}.provenance.intoto.json"
    metadata_path = output_dir / f"{target}.build-metadata.json"
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": f"mara-quality:{target}",
                "digest": {"sha256": match.group(1)},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v0.2",
        "predicate": provenance,
    }
    _write_json(statement_path, statement)
    _write_json(metadata_path, metadata)
    return statement_path, metadata_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Retain digest-bound provenance from Docker Buildx metadata."
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--metadata-env", default="BUILD_METADATA")
    args = parser.parse_args(argv)

    source = os.environ.get(args.metadata_env, "")
    if not source:
        raise SystemExit(f"Missing Buildx metadata environment: {args.metadata_env}")
    try:
        metadata = json.loads(source)
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid Buildx metadata JSON: {error}") from error
    if not isinstance(metadata, dict):
        raise SystemExit("Buildx metadata must be a JSON object")
    try:
        generate_container_evidence(
            metadata,
            target=args.target,
            output_dir=args.output_dir,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
