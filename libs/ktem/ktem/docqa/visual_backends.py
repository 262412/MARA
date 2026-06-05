from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

from .visual_retriever import LocalLateInteractionVisualRetriever


@dataclass(frozen=True)
class VisualBackendSpec:
    name: str
    role: str
    status: str
    backend_type: str
    benchmark_ready: bool
    builder: Callable[[], Any] | None = None
    available: Callable[[], bool] | None = None
    readiness_reason: str = ""

    def as_health(self) -> dict[str, Any]:
        status = self.status
        benchmark_ready = self.benchmark_ready
        if self.available is not None:
            status = "configured" if self.available() else "not_configured"
            benchmark_ready = benchmark_ready and status == "configured"
        return {
            "name": self.name,
            "role": self.role,
            "status": status,
            "backend_type": self.backend_type,
            "benchmark_ready": benchmark_ready,
            **_readiness_reason(status, self.readiness_reason),
        }


class ColVisionVisualRetriever:
    backend_type = "colvision_multi_vector"

    def __init__(self, name: str, model_family: str, model_name: str) -> None:
        self.name = name
        self.model_family = model_family
        self.model_name = model_name

    def score(self, query: str, record: dict[str, Any]) -> float:
        del query
        metadata = dict(record.get("metadata") or {})
        page_score = (
            metadata.get("page_level_score")
            or metadata.get("colvision_score")
            or record.get("page_level_score")
        )
        if page_score is not None:
            return float(page_score)
        return 0.0


_RETRIEVERS: dict[str, VisualBackendSpec] = {
    "local_late_interaction": VisualBackendSpec(
        name="local_late_interaction",
        role="visual_retriever",
        status="configured",
        backend_type="deterministic_smoke",
        benchmark_ready=True,
        builder=LocalLateInteractionVisualRetriever,
    ),
    "colpali": VisualBackendSpec(
        name="colpali",
        role="visual_retriever",
        status="not_configured",
        backend_type="colvision_multi_vector",
        benchmark_ready=True,
        builder=lambda: ColVisionVisualRetriever(
            "colpali",
            "colpali",
            "vidore/colpali-v1.2",
        ),
        available=lambda: False,
        readiness_reason="requires_real_colvision_inference_backend",
    ),
    "colqwen": VisualBackendSpec(
        name="colqwen",
        role="visual_retriever",
        status="not_configured",
        backend_type="colvision_multi_vector",
        benchmark_ready=True,
        builder=lambda: ColVisionVisualRetriever(
            "colqwen",
            "colqwen",
            "vidore/colqwen2-v1.0",
        ),
        available=lambda: False,
        readiness_reason="requires_real_colvision_inference_backend",
    ),
}
_GENERATORS: dict[str, VisualBackendSpec] = {
    "evidence_only_without_vlm": VisualBackendSpec(
        name="evidence_only_without_vlm",
        role="visual_generator",
        status="evidence_only",
        backend_type="none",
        benchmark_ready=True,
        builder=None,
    )
}


def build_visual_retriever_backend(backend_name: str):
    return _build_backend(backend_name, _RETRIEVERS, "visual retriever")


def build_visual_generator_backend(backend_name: str):
    backend = str(backend_name or "").strip()
    if not backend:
        return None
    if backend in _GENERATORS:
        spec = _GENERATORS[backend]
        return spec.builder() if spec.builder else None
    return _instantiate_dotted_backend(backend, "visual generator")


def visual_backend_health(config: dict[str, Any]) -> dict[str, Any]:
    retriever_name = str(config.get("visual_retriever_backend") or "").strip()
    generator_name = _visual_generator_name(config)
    requires_config = _bool_value(config.get("requires_backend_config"))

    backends = {
        "visual_retriever": _backend_health(
            retriever_name,
            _RETRIEVERS,
            "visual_retriever",
        ),
        "visual_generator": _backend_health(
            generator_name,
            _GENERATORS,
            "visual_generator",
        ),
    }
    missing = _missing_backends(backends, requires_config)
    return {
        "backend_status": "not_configured" if missing else "configured",
        "requires_backend_config": requires_config,
        "missing_backends": missing,
        "backends": backends,
    }


def _build_backend(
    backend_name: str,
    registry: dict[str, VisualBackendSpec],
    label: str,
):
    backend = str(backend_name or "").strip()
    if not backend:
        return None
    spec = registry.get(backend)
    if spec is not None:
        return spec.builder() if spec.builder else None
    return _instantiate_dotted_backend(backend, label)


def _visual_generator_name(config: dict[str, Any]) -> str:
    explicit = str(config.get("visual_generator_backend") or "").strip()
    if explicit:
        return explicit
    route_policy = str(config.get("route_policy") or "").strip().lower()
    if route_policy in {"visual", "page_image", "page-image"}:
        return str(config.get("generator_backend") or "").strip()
    return ""


def _backend_health(
    backend_name: str,
    registry: dict[str, VisualBackendSpec],
    role: str,
) -> dict[str, Any]:
    backend = str(backend_name or "").strip()
    if not backend:
        return {
            "name": "",
            "role": role,
            "status": "not_configured",
            "backend_type": "",
            "benchmark_ready": False,
        }
    spec = registry.get(backend)
    if spec is not None:
        return spec.as_health()
    return _dotted_backend_health(backend, role)


def _dotted_backend_health(backend: str, role: str) -> dict[str, Any]:
    status = "configured" if _dotted_backend_available(backend) else "not_configured"
    return {
        "name": backend,
        "role": role,
        "status": status,
        "backend_type": "dotted",
        "benchmark_ready": status == "configured",
    }


def _readiness_reason(status: str, reason: str) -> dict[str, str]:
    if status == "configured" or not reason:
        return {}
    return {"readiness_reason": reason}


def _missing_backends(
    backends: dict[str, dict[str, Any]],
    requires_config: bool,
) -> list[str]:
    missing = []
    for role, health in backends.items():
        status = str(health.get("status") or "")
        if status == "not_configured":
            missing.append(role)
        elif (
            requires_config and role == "visual_generator" and status == "evidence_only"
        ):
            missing.append(role)
    return missing


def _instantiate_dotted_backend(backend: str, label: str):
    module_name, _, attr_name = backend.rpartition(".")
    if not module_name or not attr_name:
        raise ValueError(
            f"Configured {label} backend must be a dotted import path: {backend}"
        )
    module = importlib.import_module(module_name)
    target = getattr(module, attr_name)
    return target() if isinstance(target, type) else target


def _dotted_backend_available(backend: str) -> bool:
    module_name, _, attr_name = backend.rpartition(".")
    if not module_name or not attr_name:
        return False
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return False
    return hasattr(module, attr_name)


def _colpali_available() -> bool:
    return importlib.util.find_spec("colpali_engine") is not None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)
