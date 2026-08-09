from __future__ import annotations


def configure_docqa_runtime_profile(
    *,
    include_query_features: bool,
    include_file_artifacts: bool | None,
    reasoning_paths: tuple[str, ...] | None,
) -> None:
    if (
        include_query_features
        and include_file_artifacts is None
        and reasoning_paths is None
    ):
        return

    from theflow.settings import settings as flowsettings

    if not include_query_features:
        flowsettings.KH_REASONINGS = []
        flowsettings.KH_WEB_SEARCH_BACKEND = ""
    elif reasoning_paths is not None:
        flowsettings.KH_REASONINGS = list(reasoning_paths)
    if include_file_artifacts is not None:
        flowsettings.KH_FILE_INDEX_ARTIFACTS_ENABLED = include_file_artifacts
