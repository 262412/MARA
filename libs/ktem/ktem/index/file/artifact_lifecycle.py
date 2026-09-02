from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kotaemon import artifact_pipeline
from kotaemon.artifact_namespace import finish_and_publish_artifacts


def begin_file_artifacts(
    pipeline: Any,
    extra_info: dict,
    settings: Any,
) -> str | None:
    return artifact_pipeline.begin_indexing_artifacts(
        pipeline,
        extra_info,
        enabled=_enabled(settings),
    )


def finish_file_artifacts(
    pipeline: Any,
    file_id: object,
    source_path: str | Path,
    settings: Any,
) -> None:
    if _enabled(settings):
        finish_and_publish_artifacts(pipeline, file_id, source_path, settings)
    else:
        artifact_pipeline.finish_indexing(pipeline, file_id, source_path)


def _enabled(settings: Any) -> bool:
    # The secure artifact filesystem requires POSIX directory-fd operations.
    return bool(
        getattr(settings, "KH_FILE_INDEX_ARTIFACTS_ENABLED", os.name == "posix")
    )


__all__ = ["begin_file_artifacts", "finish_file_artifacts"]
