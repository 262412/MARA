"""File publication for derived graph snapshots; this is not a freshness lease."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
