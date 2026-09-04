from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def benchmark_index_contract(manifest_path: str | Path) -> str:
    manifest = Path(manifest_path).resolve()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ValueError("benchmark manifest documents must be a list")

    digest = hashlib.sha256()
    _update_file(digest, manifest, label="manifest")
    records = sorted(
        (_document_record(item) for item in documents),
        key=lambda record: (record[0], str(record[1])),
    )
    for document_id, document_path in records:
        digest.update(f"\ndocument_id:{document_id}\n".encode("utf-8"))
        _update_file(digest, document_path, label="document")
    return f"sha256:{digest.hexdigest()}"


def _document_record(value: Any) -> tuple[str, Path]:
    if not isinstance(value, dict):
        raise ValueError("benchmark manifest document entries must be objects")
    document_id = str(value.get("document_id") or "").strip()
    raw_path = str(value.get("path") or "").strip()
    if not document_id or not raw_path:
        raise ValueError("benchmark document requires document_id and path")
    path = Path(raw_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"benchmark document missing: {path}")
    return document_id, path


def _update_file(digest: Any, path: Path, *, label: str) -> None:
    digest.update(f"{label}:{path.stat().st_size}\n".encode("utf-8"))
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: benchmark_index_contract.py MANIFEST", file=sys.stderr)
        return 2
    try:
        print(benchmark_index_contract(argv[1]))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
