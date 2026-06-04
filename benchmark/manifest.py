from __future__ import annotations

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
    },
]


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


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
                evidence_pages=_ensure_list(record.get("evidence_pages")),
                evidence_sources=[
                    str(item).strip()
                    for item in _ensure_list(record.get("evidence_sources"))
                    if str(item).strip()
                ],
                gold_evidence=[
                    dict(item)
                    for item in _ensure_list(record.get("gold_evidence"))
                    if isinstance(item, dict)
                ],
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
        "route_policy",
        "planner_model",
        "allowed_routes",
        "verification_mode",
        "text_retriever_backend",
        "visual_retriever_backend",
        "visual_backend_type",
        "graph_backend",
        "planner_backend",
        "generator_backend",
        "backend_status",
        "requires_backend_config",
        "missing_backends",
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

        gold_evidence = [
            dict(item)
            for item in _ensure_list(record.get("gold_evidence"))
            if isinstance(item, dict)
        ]
        evidence_pages = _ensure_list(record.get("evidence_pages"))
        evidence_sources = [
            str(item).strip()
            for item in _ensure_list(record.get("evidence_sources"))
            if str(item).strip()
        ]
        if not evidence_pages:
            evidence_pages = [
                item["page"] for item in gold_evidence if item.get("page") is not None
            ]
        if not evidence_sources:
            evidence_sources = [
                str(item["citation"]).strip()
                for item in gold_evidence
                if str(item.get("citation") or "").strip()
            ]

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
