from __future__ import annotations

import base64
import importlib
import json
import mimetypes
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
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


class ColVisionHTTPVisualRetriever:
    backend_type = "colvision_multi_vector"

    def __init__(
        self,
        name: str,
        model_family: str,
        *,
        endpoint: str | None = None,
        timeout: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.name = name
        self.model_family = model_family
        self.endpoint = endpoint or _colvision_endpoint(model_family)
        self.timeout = timeout or float(os.getenv("MARA_COLVISION_TIMEOUT", "60"))
        self.batch_size = batch_size or _colvision_batch_size()

    def score(self, query: str, record: dict[str, Any]) -> float:
        return self.score_many(query, [record])[0]

    def score_many(self, query: str, records: list[dict[str, Any]]) -> list[float]:
        scores = [0.0 for _ in records]
        pending = [
            (index, image_url)
            for index, record in enumerate(records)
            if (image_url := _image_url(record))
        ]
        for chunk in _chunks(pending, self.batch_size):
            response = self._post_json(
                {
                    "query": str(query or ""),
                    "images": [image_url for _, image_url in chunk],
                    "model_family": self.model_family,
                }
            )
            raw_scores = response.get("scores") if isinstance(response, dict) else None
            if not isinstance(raw_scores, list):
                continue
            for (index, _), score in zip(chunk, raw_scores):
                scores[index] = round(float(score), 4)
        return scores

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class QwenVLVisualGenerator:
    name = "local_qwen3_vl"
    backend_type = "openai_compatible_vlm"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_images: int | None = None,
        max_output_tokens: int | None = None,
        max_evidence_text_chars: int | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv(
            "MARA_VLM_BASE_URL", "http://localhost:8001/v1"
        )
        self.api_key = api_key or os.getenv("MARA_VLM_API_KEY", "local")
        self.model = model or os.getenv("MARA_VLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
        self.timeout = timeout or float(os.getenv("MARA_VLM_TIMEOUT", "60"))
        self.max_images = _max_images(max_images)
        self.max_output_tokens = _max_output_tokens(max_output_tokens)
        self.max_evidence_text_chars = _max_evidence_text_chars(max_evidence_text_chars)

    def generate(self, request: Any, bundle: Any) -> str:
        items = [
            item for item in getattr(bundle, "items", []) if isinstance(item, dict)
        ]
        content = [
            {
                "type": "text",
                "text": _visual_prompt(
                    request,
                    items,
                    max_text_chars=self.max_evidence_text_chars,
                ),
            }
        ]
        content.extend(_image_parts(items, limit=self.max_images))
        response = self._client().chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=_effective_max_output_tokens(request, self.max_output_tokens),
        )
        return str(response.choices[0].message.content or "").strip()

    def _client(self):
        from openai import OpenAI

        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )


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
        builder=lambda: ColVisionHTTPVisualRetriever(
            "colpali",
            "colpali",
        ),
        available=lambda: _colvision_http_available(
            _colvision_endpoint("colpali"), "colpali"
        ),
        readiness_reason="requires_local_colvision_http_server",
    ),
    "colqwen": VisualBackendSpec(
        name="colqwen",
        role="visual_retriever",
        status="not_configured",
        backend_type="colvision_multi_vector",
        benchmark_ready=True,
        builder=lambda: ColVisionHTTPVisualRetriever(
            "colqwen",
            "colqwen",
        ),
        available=lambda: _colvision_http_available(
            _colvision_endpoint("colqwen"), "colqwen"
        ),
        readiness_reason="requires_local_colvision_http_server",
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
    ),
    "local_qwen3_vl": VisualBackendSpec(
        name="local_qwen3_vl",
        role="visual_generator",
        status="configured",
        backend_type="openai_compatible_vlm",
        benchmark_ready=True,
        builder=QwenVLVisualGenerator,
        available=lambda: _openai_compatible_vlm_available(_vlm_base_url()),
        readiness_reason="requires_local_openai_compatible_vlm_server",
    ),
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
    missing = _missing_backends(
        backends,
        requires_config,
        allow_evidence_only_generator=_allow_evidence_only_generator(config),
    )
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
    *,
    allow_evidence_only_generator: bool = False,
) -> list[str]:
    missing = []
    for role, health in backends.items():
        status = str(health.get("status") or "")
        if status == "not_configured":
            missing.append(role)
        elif (
            requires_config and role == "visual_generator" and status == "evidence_only"
        ):
            if not allow_evidence_only_generator:
                missing.append(role)
    return missing


def _allow_evidence_only_generator(config: dict[str, Any]) -> bool:
    if (
        "use_generation" in config
        and _bool_value(config.get("use_generation")) is False
    ):
        return True
    benchmark_role = str(config.get("benchmark_role") or "").strip().lower()
    return benchmark_role in {"retrieval_diagnostic", "retriever_diagnostic"}


def _max_images(explicit: int | None) -> int:
    raw_value: Any = explicit
    if raw_value is None:
        raw_value = os.getenv("MARA_VLM_MAX_IMAGES", "1")
    return max(1, int(raw_value))


def _max_output_tokens(explicit: int | None) -> int:
    raw_value: Any = explicit
    if raw_value is None:
        raw_value = os.getenv("MARA_VLM_MAX_OUTPUT_TOKENS", "256")
    return max(1, int(raw_value))


def _max_evidence_text_chars(explicit: int | None) -> int:
    raw_value: Any = explicit
    if raw_value is None:
        raw_value = os.getenv("MARA_VLM_EVIDENCE_TEXT_CHARS", "600")
    return max(0, int(raw_value))


def _colvision_batch_size() -> int:
    return max(1, int(os.getenv("MARA_COLVISION_BATCH_SIZE", "8")))


def _chunks(items: list[Any], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


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


def _visual_prompt(
    request: Any,
    items: list[dict[str, Any]],
    *,
    max_text_chars: int,
) -> str:
    prompt = str(getattr(request, "prompt", "") or "").strip()
    evidence = []
    for item in items[:4]:
        evidence_id = str(item.get("evidence_id") or "").strip()
        page = str(item.get("page_label") or item.get("page_number") or "").strip()
        source = str(item.get("file_name") or item.get("source_name") or "").strip()
        text = _truncate_text(
            str(
                item.get("ocr_text") or item.get("text") or item.get("vlm_text") or ""
            ).strip(),
            max_text_chars,
        )
        label = " ".join(
            part for part in [source, f"page {page}" if page else ""] if part
        )
        if evidence_id:
            label = f"{label} evidence_id={evidence_id}".strip()
        if text:
            evidence.append(f"- {label}: {text}" if label else f"- {text}")
        elif label:
            evidence.append(f"- {label}")
    evidence_text = "\n".join(evidence) if evidence else "- No text evidence provided."
    if _is_benchmark_gold_answer_request(request, prompt):
        return (
            "Answer the benchmark visual QA request using the page image and OCR "
            "evidence. Preserve the benchmark gold-answer contract below. Return "
            "only the shortest answer span. Do not return JSON, markdown, "
            "references, explanations, or surrounding prose.\n\n"
            f"{prompt}\n\nEvidence:\n{evidence_text}"
        )
    return (
        "Answer the user's question using the provided page image evidence. "
        "If the image evidence is insufficient, say so.\n\n"
        f"Question: {prompt}\n\nEvidence:\n{evidence_text}"
    )


def _is_benchmark_gold_answer_request(request: Any, prompt: str) -> bool:
    return (
        str(getattr(request, "origin", "") or "").strip() == "benchmark"
        or "Benchmark gold-answer contract:" in prompt
    )


def _effective_max_output_tokens(request: Any, configured: int) -> int:
    prompt = str(getattr(request, "prompt", "") or "")
    if _is_benchmark_gold_answer_request(request, prompt):
        return min(configured, 48)
    return configured


def _truncate_text(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()} [truncated]"


def _image_parts(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("modality") or "") != "page_image":
            continue
        image_url = _image_url(item)
        if not image_url:
            continue
        parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if len(parts) >= limit:
            break
    return parts


def _image_url(item: dict[str, Any]) -> str:
    image_ref = str(
        item.get("page_image_path")
        or item.get("rendered_page_image")
        or item.get("image_ref")
        or dict(item.get("metadata") or {}).get("image_ref")
        or ""
    ).strip()
    if image_ref.startswith(("data:", "http://", "https://")):
        return image_ref
    if not image_ref:
        return ""
    path = Path(image_ref)
    if not path.is_file():
        return ""
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _colvision_endpoint(model_family: str) -> str:
    family = str(model_family or "").strip().lower()
    family_env = f"MARA_{family.upper()}_ENDPOINT" if family else ""
    if family_env:
        endpoint = os.getenv(family_env)
        if endpoint:
            return endpoint
    return os.getenv("MARA_COLVISION_ENDPOINT", "http://127.0.0.1:8003/visual-score")


def _vlm_base_url() -> str:
    return os.getenv("MARA_VLM_BASE_URL", "http://localhost:8001/v1")


def _colvision_http_available(endpoint: str, model_family: str) -> bool:
    health_endpoint = endpoint.rsplit("/", 1)[0] + "/health"
    try:
        with urllib.request.urlopen(health_endpoint, timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False
    if not payload.get("ok"):
        return False
    served_family = str(payload.get("model_family") or "").strip()
    return not served_family or served_family == model_family


def _openai_compatible_vlm_available(base_url: str) -> bool:
    models_endpoint = str(base_url or "").rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(models_endpoint, timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and isinstance(payload.get("data"), list)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)
