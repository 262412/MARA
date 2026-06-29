from __future__ import annotations

from typing import Any


def limit_unique_strings(values: list[str], limit: int) -> list[str]:
    seen = set()
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def build_file_graph(
    service: Any, file_id: str, source: dict[str, Any]
) -> dict[str, Any]:
    docs = service._load_file_docs(file_id)
    candidates, pages_seen = service._make_sentence_candidates(docs)
    candidates, top_keywords = service._score_candidates(candidates)

    llm_outline = service._generate_outline_with_llm(
        source.get("name", file_id), candidates[:16]
    )
    file_points = _build_llm_file_points(service, file_id, candidates, llm_outline)
    if file_points is None:
        file_points = _build_candidate_file_points(
            service, file_id, source, candidates, top_keywords
        )
    summary_text, summary_candidate, knowledge_points = file_points

    summary_pages = limit_unique_strings(
        [summary_candidate.get("page_label", "")] + pages_seen,
        12,
    )
    summary_chunks = limit_unique_strings([summary_candidate.get("doc_id", "")], 12)

    return {
        "file_id": file_id,
        "file_name": source.get("name", file_id),
        "signature": service._make_signature(source),
        "summary": summary_text,
        "pages": pages_seen,
        "top_keywords": top_keywords,
        "summary_support_pages": {file_id: summary_pages},
        "summary_support_chunk_ids": {file_id: summary_chunks},
        "support_pages": {file_id: summary_pages},
        "support_chunk_ids": {file_id: summary_chunks},
        "evidence_pages": {file_id: list(summary_pages)},
        "evidence_chunk_ids": {file_id: list(summary_chunks)},
        "knowledge_points": knowledge_points,
    }


def _build_file_knowledge_point(
    *,
    file_id: str,
    index: int,
    label: str,
    keywords: list[str],
    support_pages: list[str],
    support_chunk_ids: list[str],
) -> dict[str, Any]:
    return {
        "id": f"point::{file_id}::{index}",
        "type": "knowledge_point",
        "file_id": file_id,
        "label": label,
        "keywords": limit_unique_strings(keywords, 6),
        "related_file_ids": [file_id],
        "support_pages": {file_id: support_pages},
        "support_chunk_ids": {file_id: support_chunk_ids},
        "evidence_pages": {file_id: list(support_pages)},
        "evidence_chunk_ids": {file_id: list(support_chunk_ids)},
    }


def _build_llm_file_points(
    service: Any,
    file_id: str,
    candidates: list[dict[str, Any]],
    llm_outline: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]] | None:
    if not llm_outline or not llm_outline.get("knowledge_points"):
        return None

    summary_text = service._trim_sentence(llm_outline.get("summary", ""), 132)
    if not summary_text and candidates:
        summary_text = service._trim_sentence(candidates[0].get("text", ""), 132)
    summary_candidate = (
        candidates[0] if candidates else {"page_label": "", "doc_id": ""}
    )

    knowledge_points: list[dict[str, Any]] = []
    for point in llm_outline.get("knowledge_points", []):
        label = service._trim_sentence(str(point.get("label", "") or ""), 110)
        if not label or service._is_duplicate_point(knowledge_points, label):
            continue
        match = (
            candidates[len(knowledge_points)]
            if len(candidates) > len(knowledge_points)
            else summary_candidate
        )
        keywords = list(point.get("keywords", [])) + service._extract_keywords(
            label, limit=6
        )
        knowledge_points.append(
            _build_file_knowledge_point(
                file_id=file_id,
                index=len(knowledge_points) + 1,
                label=label,
                keywords=keywords,
                support_pages=limit_unique_strings([match.get("page_label", "")], 8),
                support_chunk_ids=limit_unique_strings([match.get("doc_id", "")], 8),
            )
        )
        if len(knowledge_points) >= 6:
            break
    if not knowledge_points:
        return None
    return summary_text, summary_candidate, knowledge_points


def _build_candidate_file_points(
    service: Any,
    file_id: str,
    source: dict[str, Any],
    candidates: list[dict[str, Any]],
    top_keywords: list[str],
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    if candidates:
        summary_candidate = candidates[0]
        summary_text = service._trim_sentence(summary_candidate.get("text", ""), 132)
    else:
        summary_text = (
            f"{source.get('name', file_id)} contains indexed content "
            "for this conversation."
        )
        summary_candidate = {"page_label": "", "doc_id": ""}

    knowledge_points: list[dict[str, Any]] = []
    for candidate in candidates:
        label = service._trim_sentence(candidate.get("text", ""), 110)
        if not label or service._is_duplicate_point(knowledge_points, label):
            continue
        knowledge_points.append(
            _build_file_knowledge_point(
                file_id=file_id,
                index=len(knowledge_points) + 1,
                label=label,
                keywords=candidate.get("keywords", []),
                support_pages=limit_unique_strings(
                    [candidate.get("page_label", "")], 8
                ),
                support_chunk_ids=limit_unique_strings(
                    [candidate.get("doc_id", "")], 8
                ),
            )
        )
        if len(knowledge_points) >= 6:
            break

    if not knowledge_points:
        knowledge_points.append(
            _build_file_knowledge_point(
                file_id=file_id,
                index=1,
                label=service._trim_sentence(summary_text, 110),
                keywords=top_keywords[:4],
                support_pages=limit_unique_strings(
                    [summary_candidate.get("page_label", "")], 8
                ),
                support_chunk_ids=limit_unique_strings(
                    [summary_candidate.get("doc_id", "")], 8
                ),
            )
        )
    return summary_text, summary_candidate, knowledge_points
