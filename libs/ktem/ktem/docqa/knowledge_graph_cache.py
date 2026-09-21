"""File publication for derived graph snapshots; this is not a freshness lease."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def storage_path(root: Path, conversation_id: str) -> Path:
    conversation_key = str(conversation_id or "draft")
    safe_key = re.sub(r"[^A-Za-z0-9_\-]", "_", conversation_key)
    return root / f"{safe_key}.json"


def load_snapshot(path: Path, defaults: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return defaults
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("Graph cache must contain a JSON object")
    except FileNotFoundError:
        return defaults
    except ValueError:
        logger.warning("Unusable graph cache: %s", path, exc_info=True)
        return defaults
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def save_snapshot(path: Path, state: dict[str, Any]) -> None:
    """Publish only a completely encoded, flushed and closed sibling file.

    A replace is the visibility boundary, not a cross-file transaction or a
    guarantee that this build is current. Callers own authorization/freshness.
    """
    stream = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(stream.name)
    try:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        os.replace(temporary, path)
    finally:
        primary = sys.exc_info()[1]
        failures = []
        for release in (stream.close, lambda: temporary.unlink(missing_ok=True)):
            try:
                release()
            except OSError as exc:
                failures.append(exc)
                logger.exception(
                    "Failed to release graph cache temporary %s", temporary
                )
        if primary is None and failures:
            raise failures[0]
