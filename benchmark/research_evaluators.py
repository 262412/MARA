from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from .research_adapters import research_adapter_metric_metadata

logger = logging.getLogger(__name__)


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
        "paper_grade": False,
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
    return metrics, {
        "backend": backend_label,
        "implementation": str(
            metadata.get("implementation") or f"{adapter_name}_external_evaluator"
        ),
        "metric_scope": "external",
        "paper_grade": bool(metadata.get("paper_grade")),
        "status": "configured",
    }


def _failed_metadata(backend_label: str, exc: Exception) -> dict[str, Any]:
    return {
        "backend": backend_label,
        "metric_scope": "external",
        "paper_grade": False,
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


def _load_evaluator(backend: Any) -> Callable[[dict[str, Any]], Any]:
    if callable(backend):
        return backend
    ref = str(backend or "").strip()
    module_name, _, attr_name = ref.rpartition(".")
    if not module_name or not attr_name:
        raise ValueError(f"Invalid evaluator backend: {ref}")
    module = importlib.import_module(module_name)
    evaluator = getattr(module, attr_name)
    if not callable(evaluator):
        raise TypeError(f"Evaluator backend is not callable: {ref}")
    return evaluator


def _backend_label(backend: Any) -> str:
    if isinstance(backend, str):
        return backend
    module = getattr(backend, "__module__", "")
    name = getattr(backend, "__qualname__", getattr(backend, "__name__", ""))
    return ".".join(item for item in (module, name) if item) or str(backend)
