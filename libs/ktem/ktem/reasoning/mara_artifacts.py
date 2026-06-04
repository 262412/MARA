from __future__ import annotations

from typing import Any

from kotaemon.base import RetrievedDocument


def build_artifact_for_pipeline(
    pipeline: Any, understanding: dict[str, Any]
) -> dict[str, Any] | None:
    artifact_type = str(getattr(pipeline, "artifact_type", "") or "").strip()
    if not artifact_type:
        task_type = str(understanding.get("task_type") or "")
        artifact_type = task_type if task_type != "qa" else ""
    if artifact_type not in _ARTIFACT_BUILDERS:
        return None
    evidence = _artifact_evidence(list(getattr(pipeline, "_mara_last_docs", [])))
    if not evidence:
        return _planned_artifact(artifact_type)
    return _ARTIFACT_BUILDERS[artifact_type](evidence)


def _excerpt(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _artifact_evidence(docs: list[RetrievedDocument]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for doc in docs:
        metadata = dict(getattr(doc, "metadata", {}) or {})
        excerpt = _excerpt(
            str(getattr(doc, "text", "") or getattr(doc, "content", "") or "")
        )
        if not excerpt:
            continue
        evidence.append(
            {
                "evidence_id": str(getattr(doc, "doc_id", "") or "").strip(),
                "file_id": str(metadata.get("file_id") or "").strip(),
                "file_name": str(metadata.get("file_name") or "").strip(),
                "page_label": str(metadata.get("page_label") or "").strip(),
                "excerpt": excerpt,
            }
        )
    return evidence


def _evidence_label(item: dict[str, Any]) -> str:
    label = str(item.get("file_name") or item.get("evidence_id") or "source")
    page = str(item.get("page_label") or "").strip()
    return f"{label} p.{page}" if page else label


def _source_ids(item: dict[str, Any]) -> list[str]:
    file_id = str(item.get("file_id") or "").strip()
    return [file_id] if file_id else []


def _topic_from_excerpt(excerpt: str) -> str:
    words = [word.strip(".,:;!?()[]{}\"'") for word in excerpt.split()]
    return next((word for word in words if word), "the source")


def _planned_artifact(artifact_type: str) -> dict[str, Any]:
    return {
        "type": artifact_type,
        "status": "planned",
        "source": "mara_reasoning",
        "cited_evidence": [],
    }


def _study_guide_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    first = evidence[0]
    concepts = [_evidence_label(item) for item in evidence[:5]]
    return {
        "type": "study_guide",
        "status": "ready",
        "source": "mara_reasoning",
        "overview": first["excerpt"],
        "key_concepts": concepts,
        "glossary": [
            {"term": _evidence_label(item), "definition": item["excerpt"]}
            for item in evidence[:5]
        ],
        "key_questions": [
            f"What does {_evidence_label(item)} show about "
            f"{_topic_from_excerpt(item['excerpt'])}?"
            for item in evidence[:5]
        ],
        "cited_evidence": evidence,
    }


def _quiz_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    first = evidence[0]
    question = f"Which statement is supported by {_evidence_label(first)}?"
    return {
        "type": "quiz",
        "status": "ready",
        "source": "mara_reasoning",
        "multiple_choice": [
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
        "short_answer": [
            {
                "question": f"Summarize the evidence from {_evidence_label(first)}.",
                "answer": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        "answer_key": [
            {
                "question": question,
                "answer": first["excerpt"],
                "explanation": first["excerpt"],
                "source_ids": _source_ids(first),
            }
        ],
        "cited_evidence": evidence,
    }


def _flashcards_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "flashcards",
        "status": "ready",
        "source": "mara_reasoning",
        "cards": [
            {
                "front": f"What is the key point from {_evidence_label(item)}?",
                "back": item["excerpt"],
                "source_ids": _source_ids(item),
            }
            for item in evidence[:10]
        ],
        "cited_evidence": evidence,
    }


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
    return {
        "type": "mindmap",
        "status": "ready",
        "source": "mara_reasoning",
        "nodes": nodes,
        "edges": [
            {"source": nodes[0]["id"], "target": node["id"]}
            for node in nodes[1:]
            if nodes
        ],
        "cited_evidence": evidence,
    }


def _slide_outline_artifact(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    slides = [
        {
            "title": _evidence_label(item),
            "bullets": [item["excerpt"]],
            "source_ids": _source_ids(item),
        }
        for item in evidence[:8]
    ]
    return {
        "type": "slide_outline",
        "status": "ready",
        "source": "mara_reasoning",
        "title": "Source-grounded MARA outline",
        "sections": [{"title": "Evidence-backed narrative", "slides": slides}],
        "cited_evidence": evidence,
    }


_ARTIFACT_BUILDERS = {
    "study_guide": _study_guide_artifact,
    "quiz": _quiz_artifact,
    "flashcards": _flashcards_artifact,
    "mindmap": _mindmap_artifact,
    "slide_outline": _slide_outline_artifact,
}
