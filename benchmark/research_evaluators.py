from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from .research_adapters import (
    research_adapter_metric_metadata,
    research_adapter_metrics,
)

logger = logging.getLogger(__name__)


class _ResearchEvaluatorAdapter:
    adapter_name = ""

    def __init__(
        self,
        backend: Callable[[dict[str, Any]], Any] | None = None,
        *,
        paper_grade: bool = False,
    ) -> None:
        self.backend = backend
        self.paper_grade = paper_grade

    def __call__(self, prediction: dict[str, Any]) -> dict[str, Any]:
        if self.backend is None:
            metrics = dict(
                research_adapter_metrics(prediction).get(self.adapter_name) or {}
            )
            metadata: dict[str, Any] = {}
        else:
            metrics, metadata = _coerce_evaluator_result(self.backend(prediction))
        paper_grade = bool(metadata.get("paper_grade", self.paper_grade))
        metadata = {
            **metadata,
            **_paper_grade_contract_metadata(
                metrics,
                paper_grade=paper_grade,
                metadata=metadata,
            ),
        }
        return {
            "metrics": metrics,
            "metadata": {
                "implementation": self.__class__.__name__,
                "metric_category": _metric_category(paper_grade),
                "paper_grade": paper_grade,
                **metadata,
            },
        }


class ALCEEvaluator(_ResearchEvaluatorAdapter):
    adapter_name = "alce"


class MMDocRAGEvaluator(_ResearchEvaluatorAdapter):
    adapter_name = "mmdocrag"


class RAGTruthEvaluator(_ResearchEvaluatorAdapter):
    adapter_name = "ragtruth"


class RagasEvaluator(_ResearchEvaluatorAdapter):
    adapter_name = "ragas"


_BUILTIN_EVALUATOR_ALIASES: dict[str, type[_ResearchEvaluatorAdapter]] = {
    "builtin:alce_proxy": ALCEEvaluator,
    "builtin:mmdocrag_proxy": MMDocRAGEvaluator,
    "builtin:ragtruth_proxy": RAGTruthEvaluator,
    "builtin:ragas_proxy": RagasEvaluator,
}


def external_research_adapter_metrics(
    prediction: dict[str, Any],
    route: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    proxy_metadata = research_adapter_metric_metadata()
    metrics: dict[str, dict[str, Any]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for adapter_name in proxy_metadata:
        backend = _adapter_backend(route, adapter_name)
        if backend is None:
            metadata[adapter_name] = _not_configured_metadata(
                proxy_metadata[adapter_name]
            )
            continue
        adapter_metrics, adapter_metadata = _run_external_evaluator(
            adapter_name,
            backend,
            prediction,
        )
        if adapter_metrics:
            metrics[adapter_name] = adapter_metrics
        metadata[adapter_name] = adapter_metadata
    return metrics, metadata


def external_research_adapter_metric_metadata(
    route: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    _, metadata = external_research_adapter_metrics({}, route)
    return metadata


def _adapter_backend(route: dict[str, Any], adapter_name: str) -> Any | None:
    for key in ("external_evaluators", "research_evaluators", "evaluator_backends"):
        value = route.get(key)
        if isinstance(value, dict) and value.get(adapter_name):
            return value[adapter_name]
    return route.get(f"{adapter_name}_evaluator")


def _not_configured_metadata(proxy_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "not_configured",
        "metric_scope": "external",
        "metric_category": "external_metric",
        "paper_grade": False,
        "paper_grade_ready": False,
        "paper_grade_blockers": ["not_configured"],
        "excluded_from_summary": True,
        "requires_external_resources": list(
            proxy_metadata.get("requires_external_resources") or []
        ),
    }


def _run_external_evaluator(
    adapter_name: str,
    backend: Any,
    prediction: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    backend_label = _backend_label(backend)
    try:
        evaluator = _load_evaluator(backend)
        result = evaluator(prediction)
    except Exception as exc:
        logger.warning("External evaluator %s failed: %s", backend_label, exc)
        return {}, _failed_metadata(backend_label, exc)

    metrics, metadata = _coerce_evaluator_result(result)
    paper_grade = bool(metadata.get("paper_grade"))
    contract_metadata = _paper_grade_contract_metadata(
        metrics,
        paper_grade=paper_grade,
        metadata=metadata,
    )
    return metrics, {
        "backend": backend_label,
        "implementation": str(
            metadata.get("implementation") or f"{adapter_name}_external_evaluator"
        ),
        "metric_scope": "external",
        "metric_category": str(
            metadata.get("metric_category") or _metric_category(paper_grade)
        ),
        "paper_grade": paper_grade,
        **contract_metadata,
        "status": "configured",
        **_external_scoring_metadata(metadata),
    }


def _failed_metadata(backend_label: str, exc: Exception) -> dict[str, Any]:
    return {
        "backend": backend_label,
        "metric_scope": "external",
        "metric_category": "external_metric",
        "paper_grade": False,
        "paper_grade_ready": False,
        "paper_grade_blockers": ["failed"],
        "status": "failed",
        "error": str(exc),
        "excluded_from_summary": True,
    }


def _coerce_evaluator_result(result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(result, dict):
        return {}, {}
    if isinstance(result.get("metrics"), dict):
        metadata = result.get("metadata")
        return (
            dict(result["metrics"]),
            dict(metadata) if isinstance(metadata, dict) else {},
        )
    return dict(result), {}


def _external_scoring_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metadata[key]
        for key in ("contract_id", "primary_metric", "scoring_mode")
        if key in metadata
    }


def _paper_grade_contract_metadata(
    metrics: dict[str, Any],
    *,
    paper_grade: bool,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    blockers: list[str] = []
    if not paper_grade:
        blockers.append("not_paper_grade")
    primary_metric = str(metadata.get("primary_metric") or "").strip()
    if paper_grade and not primary_metric:
        blockers.append("missing_primary_metric")
    if primary_metric and primary_metric not in metrics:
        blockers.append("primary_metric_missing_from_metrics")
    return {
        "paper_grade_ready": bool(paper_grade and not blockers),
        "paper_grade_blockers": blockers,
    }


def _load_evaluator(backend: Any) -> Callable[[dict[str, Any]], Any]:
    if callable(backend):
        return backend
    ref = str(backend or "").strip()
    if ref.startswith("builtin:"):
        evaluator_class = _BUILTIN_EVALUATOR_ALIASES.get(ref)
        if evaluator_class is None:
            raise ValueError(f"Unknown builtin evaluator backend: {ref}")
        return evaluator_class()
    module_name, _, attr_name = ref.rpartition(".")
    if not module_name or not attr_name:
        raise ValueError(f"Invalid evaluator backend: {ref}")
    module = importlib.import_module(module_name)
    evaluator = getattr(module, attr_name)
    if isinstance(evaluator, type):
        evaluator = evaluator()
    if not callable(evaluator):
        raise TypeError(f"Evaluator backend is not callable: {ref}")
    return evaluator


def _backend_label(backend: Any) -> str:
    if isinstance(backend, str):
        return backend
    module = getattr(backend, "__module__", "")
    name = getattr(backend, "__qualname__", getattr(backend, "__name__", ""))
    return ".".join(item for item in (module, name) if item) or str(backend)


def _metric_category(paper_grade: bool) -> str:
    return "paper_grade_metric" if paper_grade else "external_metric"
