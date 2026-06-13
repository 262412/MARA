from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Iterable

from .schemas import (
    BenchmarkDocument,
    BenchmarkExample,
    ManifestBundle,
    normalize_engine_name,
    normalize_scope,
)

DEFAULT_MARA_ROUTES: list[dict[str, Any]] = [
    {
        "route_id": "direct_answer",
        "route_name": "Direct answer",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "direct",
        "allowed_routes": ["direct"],
        "verification_mode": "light",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_direct",
        "benchmark_role": "diagnostic",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "text_rag",
        "route_name": "Text RAG",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "doc",
        "allowed_routes": ["doc_text"],
        "verification_mode": "light",
        "text_retriever_backend": "docqa_text",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_docqa_generator",
        "benchmark_role": "qa_quality",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "page_image_rag_smoke",
        "route_name": "Page-image RAG smoke",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "visual",
        "allowed_routes": ["doc_page_image"],
        "verification_mode": "light",
        "visual_retriever_backend": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
        "planner_backend": "heuristic_local",
        "generator_backend": "evidence_only_without_vlm",
        "implementation_stage": "deterministic_page_image_smoke",
        "benchmark_role": "diagnostic",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "page_image_rag_vlm",
        "route_name": "Page-image RAG VLM",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "visual",
        "allowed_routes": ["doc_page_image"],
        "verification_mode": "light",
        "visual_retriever_backend": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
        "planner_backend": "heuristic_local",
        "generator_backend": "evidence_only_without_vlm",
        "backend_status": "not_configured",
        "requires_backend_config": True,
        "missing_backends": ["colpali", "visual_generator"],
        "implementation_stage": "requires_configured_visual_backends",
        "benchmark_role": "diagnostic",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "element_rag",
        "route_name": "Element RAG",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "element",
        "allowed_routes": ["doc_element"],
        "verification_mode": "light",
        "text_retriever_backend": "docqa_element_metadata",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_docqa_generator",
        "implementation_stage": "prototype_element_metadata_index",
        "benchmark_role": "prototype",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "graph_rag_local",
        "route_name": "GraphRAG local",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "graph",
        "allowed_routes": ["graph_global"],
        "verification_mode": "light",
        "graph_backend": "local_graph_index",
        "graph_mode": "local",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_graph_summary",
        "implementation_stage": "prototype_lightweight_graph_selector",
        "benchmark_role": "prototype",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "graph_rag_global",
        "route_name": "GraphRAG global",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "task_type": "summary",
        "controller_mode": "llm",
        "route_policy": "graph",
        "allowed_routes": ["graph_global"],
        "verification_mode": "light",
        "graph_backend": "local_graph_index",
        "graph_mode": "global",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_graph_summary",
        "implementation_stage": "prototype_lightweight_graph_selector",
        "benchmark_role": "prototype",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "hybrid_rag",
        "route_name": "Hybrid RAG",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "hybrid",
        "allowed_routes": ["hybrid"],
        "verification_mode": "light",
        "text_retriever_backend": "docqa_text",
        "visual_retriever_backend": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_docqa_generator",
        "benchmark_role": "qa_quality",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "controller_auto",
        "route_name": "Controller auto",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "controller_mode": "llm",
        "route_policy": "auto",
        "verification_mode": "light",
        "text_retriever_backend": "docqa_text",
        "visual_retriever_backend": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
        "graph_backend": "local_global_graph",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_docqa_generator",
        "benchmark_role": "qa_quality",
        "docqa_citation_mode": "inline",
    },
    {
        "route_id": "crag_guarded",
        "route_name": "CRAG guarded",
        "engine": "docqa_runtime",
        "scope": "multi_document",
        "reasoning_type": "mara",
        "agent_mode": "thorough",
        "controller_mode": "llm",
        "route_policy": "auto",
        "verification_mode": "strict",
        "text_retriever_backend": "docqa_text",
        "visual_retriever_backend": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
        "graph_backend": "local_global_graph",
        "planner_backend": "heuristic_local",
        "generator_backend": "local_docqa_generator",
        "benchmark_role": "qa_quality",
        "docqa_citation_mode": "inline",
    },
]


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_page_value(value: Any) -> int | str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return text


def _append_unique(target: list[Any], value: Any) -> None:
    if value not in (None, "") and value not in target:
        target.append(value)


def _legacy_financebench_evidence_from_source(
    value: str,
    *,
    document_id: str,
) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not (text.startswith("{") and "evidence_" in text):
        return None
    try:
        payload = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    page = _normalize_page_value(
        payload.get("evidence_page_num")
        or payload.get("page")
        or payload.get("page_number")
    )
    span = str(
        payload.get("evidence_text") or payload.get("text") or payload.get("span") or ""
    ).strip()
    citation = f"{document_id}#page:{page}" if page is not None else ""
    evidence: dict[str, Any] = {"document_id": document_id}
    if page is not None:
        evidence["page"] = page
    if citation:
        evidence["citation"] = citation
    if span:
        evidence["span"] = span
    return evidence if len(evidence) > 1 else None


def _coerce_evidence_fields(
    record: dict[str, Any],
    *,
    document_id: str,
) -> tuple[list[Any], list[str], list[dict[str, Any]]]:
    gold_evidence = [
        dict(item)
        for item in _ensure_list(record.get("gold_evidence"))
        if isinstance(item, dict)
    ]
    raw_sources = [
        str(item).strip()
        for item in _ensure_list(record.get("evidence_sources"))
        if str(item).strip()
    ]
    legacy_evidence = [
        item
        for source in raw_sources
        for item in [
            _legacy_financebench_evidence_from_source(
                source,
                document_id=document_id,
            )
        ]
        if item is not None
    ]
    if legacy_evidence and not gold_evidence:
        gold_evidence = legacy_evidence

    evidence_pages = list(_ensure_list(record.get("evidence_pages")))
    if not evidence_pages:
        for item in gold_evidence:
            page = item.get("page")
            if page is None:
                page = item.get("page_number")
            if page is not None:
                _append_unique(evidence_pages, _normalize_page_value(page))

    if legacy_evidence:
        evidence_sources: list[str] = []
        for item in gold_evidence:
            citation = str(item.get("citation") or "").strip()
            if citation:
                _append_unique(evidence_sources, citation)
        for source in raw_sources:
            if (
                _legacy_financebench_evidence_from_source(
                    source,
                    document_id=document_id,
                )
                is None
            ):
                _append_unique(evidence_sources, source)
    else:
        evidence_sources = list(raw_sources)

    if not evidence_sources:
        for item in gold_evidence:
            citation = str(item.get("citation") or "").strip()
            if citation:
                _append_unique(evidence_sources, citation)

    return evidence_pages, evidence_sources, gold_evidence


def _resolve_path(manifest_path: Path, document_path: str) -> Path:
    path = Path(document_path)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def _coerce_expected_formats(record: dict[str, Any]) -> list[str]:
    return [
        str(item).strip()
        for item in _ensure_list(
            record.get("expected_formats") or record.get("expected_format")
        )
        if str(item).strip()
    ]


def _coerce_expected_guardrails(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("expected_guardrails")
    if value is None:
        value = record.get("expected_guardrail")
    return dict(value) if isinstance(value, dict) else {}


def _coerce_examples(
    records: Iterable[dict[str, Any]],
    manifest_path: Path,
) -> ManifestBundle:
    records = list(records)
    dataset_name = "custom_manifest"
    documents: dict[str, BenchmarkDocument] = {}
    examples: list[BenchmarkExample] = []

    for index, record in enumerate(records):
        document_id = str(record["document_id"])
        document_path = _resolve_path(manifest_path, str(record["document_path"]))
        format_type = str(
            record.get("format_type") or document_path.suffix.lower().lstrip(".")
        ).lower()
        dataset_name = str(record.get("dataset_name") or dataset_name)

        if document_id not in documents:
            documents[document_id] = BenchmarkDocument(
                document_id=document_id,
                path=document_path,
                format_type=format_type,
                modality=str(record.get("modality") or "text"),
                metadata=dict(record.get("document_metadata") or {}),
            )

        answers = [str(item).strip() for item in _ensure_list(record.get("answers"))]
        if not answers:
            answer = str(record.get("answer", "")).strip()
            if answer:
                answers = [answer]

        evidence_pages, evidence_sources, gold_evidence = _coerce_evidence_fields(
            record,
            document_id=document_id,
        )

        examples.append(
            BenchmarkExample(
                example_id=str(record.get("example_id") or f"{document_id}_{index}"),
                document_id=document_id,
                document_ids=[document_id],
                scope=str(record.get("scope") or "document"),
                modality=str(record.get("modality") or "text"),
                answer_type=str(record.get("answer_type") or "extractive"),
                question=str(record["question"]).strip(),
                answers=answers,
                evidence_pages=evidence_pages,
                evidence_sources=evidence_sources,
                gold_evidence=gold_evidence,
                expected_formats=_coerce_expected_formats(record),
                expected_guardrails=_coerce_expected_guardrails(record),
                metadata=dict(record.get("metadata") or {}),
            )
        )

    return ManifestBundle(
        dataset_name=dataset_name,
        manifest_path=manifest_path,
        documents=documents,
        examples=examples,
    )


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _coerce_route(record: dict[str, Any]) -> dict[str, Any]:
    route_id = str(
        record.get("route_id")
        or record.get("id")
        or record.get("route")
        or record.get("name")
        or "default"
    ).strip()
    route_name = str(record.get("route_name") or record.get("name") or route_id).strip()
    route = {
        "route_id": route_id,
        "route_name": route_name,
        "engine": normalize_engine_name(record.get("engine")),
        "scope": normalize_scope(record.get("scope")),
        "reader_mode": str(record.get("reader_mode") or "default").strip(),
        "retrieval_mode": str(record.get("retrieval_mode") or "hybrid").strip(),
        "top_k": int(record.get("top_k") or 5),
        "use_generation": _coerce_bool(record.get("use_generation"), True),
        "cost_profile": record.get("cost_profile"),
        "reasoning_type": record.get("reasoning_type") or record.get("reasoning"),
        "agent_mode": record.get("agent_mode"),
        "task_type": record.get("task_type"),
        "artifact_type": record.get("artifact_type"),
    }
    for key in (
        "controller_mode",
        "docqa_citation_mode",
        "route_policy",
        "planner_model",
        "allowed_routes",
        "verification_mode",
        "graph_mode",
        "text_retriever_backend",
        "visual_retriever_backend",
        "visual_generator_backend",
        "visual_backend_type",
        "graph_backend",
        "planner_backend",
        "generator_backend",
        "backend_status",
        "requires_backend_config",
        "missing_backends",
        "implementation_stage",
        "external_evaluators",
        "research_evaluators",
        "evaluator_backends",
        "alce_evaluator",
        "mmdocrag_evaluator",
        "ragtruth_evaluator",
        "ragas_evaluator",
        "benchmark_role",
    ):
        if key in record:
            route[key] = record.get(key)
    return route


def _coerce_v2_manifest(payload: dict[str, Any], manifest_path: Path) -> ManifestBundle:
    documents: dict[str, BenchmarkDocument] = {}
    for record in payload.get("documents", []):
        document_id = str(record["document_id"])
        document_path = _resolve_path(
            manifest_path, str(record.get("path") or record.get("document_path"))
        )
        documents[document_id] = BenchmarkDocument(
            document_id=document_id,
            path=document_path,
            format_type=str(
                record.get("format_type") or document_path.suffix.lower().lstrip(".")
            ).lower(),
            modality=str(record.get("modality") or "text"),
            metadata=dict(record.get("metadata") or {}),
        )

    examples: list[BenchmarkExample] = []
    for index, record in enumerate(payload.get("examples", [])):
        document_ids = [
            str(item)
            for item in _ensure_list(
                record.get("document_ids") or record.get("document_id")
            )
            if str(item).strip()
        ]
        if not document_ids:
            raise ValueError("v2 manifest example must include document_ids")

        answers = [str(item).strip() for item in _ensure_list(record.get("answers"))]
        if not answers:
            answer = str(record.get("answer", "")).strip()
            if answer:
                answers = [answer]

        evidence_pages, evidence_sources, gold_evidence = _coerce_evidence_fields(
            record,
            document_id=document_ids[0],
        )

        examples.append(
            BenchmarkExample(
                example_id=str(
                    record.get("example_id") or f"{document_ids[0]}_{index}"
                ),
                document_id=document_ids[0],
                document_ids=document_ids,
                scope=str(record.get("scope") or "document"),
                modality=str(record.get("modality") or "text"),
                answer_type=str(record.get("answer_type") or "extractive"),
                question=str(record["question"]).strip(),
                answers=answers,
                evidence_pages=evidence_pages,
                evidence_sources=evidence_sources,
                gold_evidence=gold_evidence,
                expected_formats=_coerce_expected_formats(record),
                expected_guardrails=_coerce_expected_guardrails(record),
                metadata=dict(record.get("metadata") or {}),
            )
        )

    return ManifestBundle(
        dataset_name=str(payload.get("dataset_name") or "custom_manifest"),
        manifest_path=manifest_path,
        documents=documents,
        examples=examples,
        schema_version=2,
        routes=[
            _coerce_route(item)
            for item in _ensure_list(
                payload.get("routes") or payload.get("route_matrix")
            )
            if isinstance(item, dict)
        ],
    )


def load_manifest(manifest_path: str | Path) -> ManifestBundle:
    manifest_path = Path(manifest_path).resolve()
    suffix = manifest_path.suffix.lower()
    raw = manifest_path.read_text(encoding="utf-8-sig")

    if suffix == ".jsonl":
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return _coerce_examples(records, manifest_path)

    payload = json.loads(raw)
    if isinstance(payload, list):
        return _coerce_examples(payload, manifest_path)

    if not isinstance(payload, dict):
        raise ValueError(f"Unsupported manifest payload type: {type(payload)!r}")

    if int(payload.get("schema_version") or 1) == 2:
        return _coerce_v2_manifest(payload, manifest_path)

    dataset_name = str(payload.get("dataset_name") or "custom_manifest")
    examples_payload = payload.get("examples", [])
    bundle = _coerce_examples(examples_payload, manifest_path)
    bundle.dataset_name = dataset_name
    return bundle


def write_manifest(
    output_path: str | Path,
    dataset_name: str,
    records: list[dict[str, Any]],
) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_name": dataset_name,
        "examples": records,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
