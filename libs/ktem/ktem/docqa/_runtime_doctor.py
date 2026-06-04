from __future__ import annotations

import logging
from typing import Any

from ._runtime_models import DocQADoctorResult

logger = logging.getLogger(__name__)


def build_doctor_result(
    *,
    app: Any,
    file_index: Any,
    knowledge_graph: Any,
    resolved_user_id: Any,
    list_files: Any,
    list_sessions: Any,
    llms_manager: Any,
    embedding_manager: Any,
    reranking_manager: Any,
) -> DocQADoctorResult:
    issues: list[str] = []
    warnings: list[str] = []
    index_name, index_id = _index_identity(file_index, issues)
    default_llm = _default_model_name(
        llms_manager,
        "LLM",
        issues,
        warnings,
    )
    default_embedding = _default_model_name(
        embedding_manager,
        "embedding model",
        issues,
        warnings,
    )
    warnings.extend(_configuration_warnings("LLM", llms_manager))
    warnings.extend(_configuration_warnings("embedding", embedding_manager))
    warnings.extend(_configuration_warnings("reranking", reranking_manager))
    file_count = _count_records(
        list_files,
        resolved_user_id,
        "indexed files",
        issues,
    )
    session_count = _count_records(
        list_sessions,
        resolved_user_id,
        "saved sessions",
        issues,
    )

    return DocQADoctorResult(
        ok=not issues,
        app_name=getattr(app, "app_name", "MARA"),
        default_user_id=resolved_user_id,
        index_name=index_name,
        index_id=index_id,
        llm_default=default_llm,
        embedding_default=default_embedding,
        file_count=file_count,
        session_count=session_count,
        graph_cache_dir=_graph_cache_dir(knowledge_graph),
        issues=issues,
        warnings=warnings,
    )


def _index_identity(file_index: Any, issues: list[str]) -> tuple[str, int | None]:
    if file_index is None:
        issues.append("No default FileIndex is available.")
        return "", None
    return str(file_index.name), file_index.id


def _default_model_name(
    manager: Any,
    label: str,
    issues: list[str],
    warnings: list[str],
) -> str:
    try:
        return str(manager.get_default_name())
    except Exception as exc:
        logger.warning("Unable to load default %s for DocQA doctor: %s", label, exc)
        if isinstance(exc, ValueError) and "No models in pool" in str(exc):
            warnings.append(
                f"No default {label} configured yet. "
                "DocQA doctor can still run before model setup."
            )
        else:
            issues.append(f"Unable to load default {label}: {exc}")
        return ""


def _configuration_warnings(label: str, manager: Any) -> list[str]:
    return [
        f"Invalid {label} configuration: {error}" for error in manager.load_errors()
    ]


def _count_records(
    loader: Any,
    resolved_user_id: Any,
    label: str,
    issues: list[str],
) -> int:
    try:
        return len(loader(user_id=resolved_user_id))
    except Exception as exc:
        logger.warning("Unable to read %s for DocQA doctor: %s", label, exc)
        issues.append(f"Unable to read {label}: {exc}")
        return 0


def _graph_cache_dir(knowledge_graph: Any) -> str:
    if knowledge_graph is None:
        return ""
    return str(knowledge_graph._storage_dir)
