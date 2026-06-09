from __future__ import annotations

from typing import Any, Callable, cast

from theflow.settings import settings as flowsettings
from theflow.utils.modules import import_dotted_string

from .artifact_models import SUPPORTED_ARTIFACT_TYPES

ArtifactBuilder = Callable[[list[dict[str, Any]]], dict[str, Any]]
ArtifactGenerationAdapter = Callable[[dict[str, Any]], dict[str, Any]]
ARTIFACT_SCHEMA_VERSION = "mara_artifact.v1"
ARTIFACT_GENERATION_ADAPTER_SETTING = "KH_MARA_ARTIFACT_GENERATION_ADAPTER"
_SCHEMA_REQUIRED: dict[str, tuple[str, ...]] = {
    "study_guide": (
        "overview",
        "learning_objectives",
        "key_concepts",
        "glossary",
        "practice_questions",
    ),
    "quiz": ("multiple_choice", "short_answer", "answer_key", "difficulty"),
    "flashcards": ("cards", "tags", "difficulty"),
    "mindmap": ("root_topic", "nodes", "edges"),
    "slide_outline": ("title", "sections"),
    "briefing_doc": ("sections",),
    "faq": ("items",),
    "timeline": ("items",),
    "custom_report": ("sections",),
    "data_table": ("columns", "rows", "row_citations", "cell_citations"),
    "infographic": ("layout", "blocks"),
    "slide_deck": ("title", "slide_outline", "slides", "export"),
    "audio_overview": ("media_status", "script"),
    "video_overview": ("media_status", "scenes"),
}


def supports_artifact_type(artifact_type: str) -> bool:
    return artifact_type in SUPPORTED_ARTIFACT_TYPES


def artifact_payload_schema(artifact_type: str) -> dict[str, Any]:
    normalized_type = str(artifact_type or "").strip()
    if normalized_type not in _SCHEMA_REQUIRED:
        raise ValueError(f"Unsupported artifact type '{artifact_type}'.")
    return {
        "type": "object",
        "required": list(_SCHEMA_REQUIRED[normalized_type]),
        "properties": {
            key: {"description": f"{normalized_type}.{key}"}
            for key in _SCHEMA_REQUIRED[normalized_type]
        },
    }


def artifact_generation_request(
    artifact_type: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_type = str(artifact_type or "").strip()
    return {
        "artifact_type": normalized_type,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "json_schema": artifact_payload_schema(normalized_type),
        "evidence": evidence,
        "prompt": _schema_first_prompt(normalized_type),
    }


def configured_artifact_generation_adapter() -> ArtifactGenerationAdapter | None:
    dotted_path = str(
        getattr(flowsettings, ARTIFACT_GENERATION_ADAPTER_SETTING, "") or ""
    ).strip()
    if not dotted_path:
        return None
    adapter = import_dotted_string(dotted_path, safe=False)
    if not callable(adapter):
        raise ValueError(
            f"{ARTIFACT_GENERATION_ADAPTER_SETTING} must resolve to a callable."
        )
    return cast(ArtifactGenerationAdapter, adapter)


def build_planned_artifact(artifact_type: str) -> dict[str, Any]:
    return {
        "type": artifact_type,
        "status": "planned",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "source": "mara_reasoning",
        "citations": [],
        "cited_evidence": [],
    }


def build_artifact_payload(
    artifact_type: str,
    evidence: list[dict[str, Any]],
    generation_adapter: ArtifactGenerationAdapter | None = None,
) -> dict[str, Any] | None:
    artifact_type = str(artifact_type or "").strip()
    builder = _ARTIFACT_BUILDERS.get(artifact_type)
    if builder is None:
        return None
    if not evidence:
        return build_planned_artifact(artifact_type)
    adapter = generation_adapter or configured_artifact_generation_adapter()
    if adapter is not None:
        request = artifact_generation_request(artifact_type, evidence)
        return _normalize_schema_payload(
            artifact_type,
            adapter(request),
            evidence,
            source="schema_adapter",
        )
    return _normalize_schema_payload(
        artifact_type,
        builder(evidence),
        evidence,
        source="mara_reasoning",
    )


def _base_artifact(
    artifact_type: str,
    evidence: list[dict[str, Any]],
    **payload: Any,
) -> dict[str, Any]:
    return {
        "type": artifact_type,
        "status": "ready",
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "source": "mara_reasoning",
        **payload,
        "citations": _payload_citations(evidence),
        "cited_evidence": evidence,
    }


def _normalize_schema_payload(
    artifact_type: str,
    payload: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    source: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Artifact generation adapter must return a JSON object.")
    missing = [key for key in _SCHEMA_REQUIRED[artifact_type] if key not in payload]
    if missing:
        raise ValueError(
            f"Artifact payload for '{artifact_type}' is missing: " + ", ".join(missing)
        )
    normalized = dict(payload)
    normalized.setdefault("type", artifact_type)
    normalized.setdefault("status", "ready")
    normalized.setdefault("schema_version", ARTIFACT_SCHEMA_VERSION)
    normalized.setdefault("source", source)
    normalized.setdefault("citations", _payload_citations(evidence))
    normalized.setdefault("cited_evidence", evidence)
    return normalized


def _schema_first_prompt(artifact_type: str) -> str:
    return "\n".join(
        [
            f"Generate a source-grounded {artifact_type.replace('_', ' ')}.",
            "Return one JSON object matching the provided json_schema.",
            "Use only the supplied evidence; do not add unsupported claims.",
            "Preserve citation_id values for traceability.",
            "Use clear sections, Markdown tables where useful, LaTeX for math, "
            "and fenced code blocks for code.",
        ]
    )


def _payload_citations(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "citation_id": str(item.get("evidence_id") or ""),
            "source_id": str(item.get("file_id") or ""),
            "source_name": str(item.get("file_name") or ""),
            "page_label": str(item.get("page_label") or ""),
        }
        for item in evidence
    ]


def _evidence_label(item: dict[str, Any]) -> str:
    label = str(item.get("file_name") or item.get("evidence_id") or "source")
    page = str(item.get("page_label") or "").strip()
    return f"{label} p.{page}" if page else label


def _source_ids(item: dict[str, Any]) -> list[str]:
    file_id = str(item.get("file_id") or "").strip()
    return [file_id] if file_id else []


def _citation_refs(item: dict[str, Any]) -> list[str]:
    evidence_id = str(item.get("evidence_id") or "").strip()
    return [evidence_id] if evidence_id else []


def _topic_from_excerpt(excerpt: str) -> str:
    words = [word.strip(".,:;!?()[]{}\"'") for word in excerpt.split()]
    return next((word for word in words if word), "the source")


def _study_guide_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    first = evidence[0]
    return _base_artifact(
        "study_guide",
        evidence,
        overview=first["excerpt"],
        learning_objectives=[
            f"Explain the evidence from {_evidence_label(item)}."
            for item in evidence[:5]
        ],
        key_concepts=[_evidence_label(item) for item in evidence[:5]],
        glossary=[
            {"term": _evidence_label(item), "definition": item["excerpt"]}
            for item in evidence[:5]
        ],
        practice_questions=[
            f"What does {_evidence_label(item)} show about "
            f"{_topic_from_excerpt(item['excerpt'])}?"
            for item in evidence[:5]
        ],
        key_questions=[
            f"What does {_evidence_label(item)} show about "
            f"{_topic_from_excerpt(item['excerpt'])}?"
            for item in evidence[:5]
        ],
    )


def _quiz_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    first = evidence[0]
    question = f"Which statement is supported by {_evidence_label(first)}?"
    return _base_artifact(
        "quiz",
        evidence,
        multiple_choice=[
            {
                "question": question,
                "options": [
                    first["excerpt"],
                    "The selected evidence does not support this.",
                    "More sources are required before answering.",
                ],
                "answer": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        short_answer=[
            {
                "question": f"Summarize the evidence from {_evidence_label(first)}.",
                "answer": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        answer_key=[
            {
                "question": question,
                "answer": first["excerpt"],
                "explanation": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        difficulty="medium",
    )


def _flashcards_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "flashcards",
        evidence,
        cards=[
            {
                "front": f"What is the key point from {_evidence_label(item)}?",
                "back": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:10]
        ],
        tags=["source-grounded"],
        difficulty="medium",
    )


def _mindmap_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [
        {
            "id": item["evidence_id"] or f"source-{index}",
            "label": _evidence_label(item),
            "summary": item["excerpt"],
            "source_ids": _source_ids(item),
        }
        for index, item in enumerate(evidence[:10], start=1)
    ]
    return _base_artifact(
        "mindmap",
        evidence,
        root_topic=_evidence_label(evidence[0]),
        nodes=nodes,
        edges=[
            {"source": nodes[0]["id"], "target": node["id"]}
            for node in nodes[1:]
            if nodes
        ],
    )


def _slide_outline_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "slide_outline",
        evidence,
        title="Source-grounded MARA outline",
        sections=[
            {
                "title": "Evidence-backed narrative",
                "slides": [_slide_from_evidence(item) for item in evidence[:8]],
            }
        ],
    )


def _briefing_doc_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "briefing_doc",
        evidence,
        sections=[
            {
                "title": _evidence_label(item),
                "summary": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:8]
        ],
    )


def _faq_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "faq",
        evidence,
        items=[
            {
                "question": f"What does {_evidence_label(item)} show?",
                "answer": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:10]
        ],
    )


def _timeline_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "timeline",
        evidence,
        items=[
            {
                "date": "",
                "event": item["excerpt"],
                "source": _evidence_label(item),
                "source_ids": _source_ids(item),
            }
            for item in evidence[:12]
        ],
    )


def _custom_report_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "custom_report",
        evidence,
        sections=[
            {
                "heading": _evidence_label(item),
                "content": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:8]
        ],
    )


def _data_table_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    columns = ["Source", "Page", "Evidence"]
    rows = [
        [
            str(item.get("file_name") or item.get("evidence_id") or "source"),
            str(item.get("page_label") or ""),
            item["excerpt"],
        ]
        for item in evidence
    ]
    return _base_artifact(
        "data_table",
        evidence,
        columns=columns,
        rows=rows,
        row_citations=[
            {
                "row": index,
                "citation_refs": _citation_refs(item),
                "source_ids": _source_ids(item),
            }
            for index, item in enumerate(evidence)
        ],
        cell_citations=[
            {
                "row": index,
                "column": column,
                "citation_refs": _citation_refs(item),
            }
            for index, item in enumerate(evidence)
            for column in columns
        ],
    )


def _infographic_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "infographic",
        evidence,
        layout="vertical",
        blocks=[
            {
                "kind": "callout",
                "title": _evidence_label(item),
                "text": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:6]
        ],
    )


def _slide_deck_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    outline = _slide_outline_artifact(evidence)
    return _base_artifact(
        "slide_deck",
        evidence,
        title=outline["title"],
        slide_outline=outline,
        slides=outline["sections"][0]["slides"],
        export={"format": "pptx", "status": "pending_adapter"},
    )


def _audio_overview_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "audio_overview",
        evidence,
        media_status="script_only",
        script=[
            {
                "speaker": "Host",
                "text": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:8]
        ],
    )


def _video_overview_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _base_artifact(
        "video_overview",
        evidence,
        media_status="script_only",
        scenes=[
            {
                "title": _evidence_label(item),
                "narration": item["excerpt"],
                "visual": "source_page",
                "source_ids": _source_ids(item),
            }
            for item in evidence[:8]
        ],
    )


def _slide_from_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _evidence_label(item),
        "bullets": [item["excerpt"]],
        "source_ids": _source_ids(item),
    }


_ARTIFACT_BUILDERS: dict[str, ArtifactBuilder] = {
    "study_guide": _study_guide_artifact,
    "quiz": _quiz_artifact,
    "flashcards": _flashcards_artifact,
    "mindmap": _mindmap_artifact,
    "slide_outline": _slide_outline_artifact,
    "briefing_doc": _briefing_doc_artifact,
    "faq": _faq_artifact,
    "timeline": _timeline_artifact,
    "custom_report": _custom_report_artifact,
    "data_table": _data_table_artifact,
    "infographic": _infographic_artifact,
    "slide_deck": _slide_deck_artifact,
    "audio_overview": _audio_overview_artifact,
    "video_overview": _video_overview_artifact,
}
