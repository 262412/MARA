from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup

from .citation_rendering import citation_from_item, citation_from_source_ref
from .citation_stage_projection import source_ref_uses_uuid_like_source


def citation_candidate_items(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for bundle_key in ("evidence_bundle", "engine_terminal_evidence_bundle"):
        evidence_bundle = prediction.get(bundle_key)
        if isinstance(evidence_bundle, dict):
            items.extend(
                item
                for item in evidence_bundle.get("items") or []
                if isinstance(item, dict)
            )
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        for key in (
            "execution_operand_evidence",
            "canonical_candidate_evidence",
            "candidate_ranked_evidence",
            "fused_evidence",
            "verified_claim_support_evidence",
            "evidence",
        ):
            items.extend(
                item
                for item in evidence_metadata.get(key) or []
                if isinstance(item, dict)
            )
    for commit_key in ("terminal_semantic_commit", "engine_terminal_commit"):
        commit = prediction.get(commit_key)
        if isinstance(commit, dict):
            items.extend(
                item
                for item in commit.get("authoritative_evidence") or []
                if isinstance(item, dict)
            )
    items.extend(
        item
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    )
    return items


def canonical_source_refs(prediction: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in citation_candidate_items(prediction):
        for source in canonical_source_backrefs(item):
            value = str(source or "").strip()
            if value and value not in refs:
                refs.append(value)
    for key in ("scored_predicted_sources", "predicted_sources"):
        for source in prediction.get(key) or []:
            value = str(source or "").strip()
            if (
                value
                and not source_ref_uses_uuid_like_source(value)
                and value not in refs
            ):
                refs.append(value)
    return refs


def canonical_source_alias_map(
    prediction: dict[str, Any],
    canonical_sources: list[str],
) -> dict[str, tuple[str, ...]]:
    canonical_ids = {
        str(source).split("#", 1)[0]
        for source in canonical_sources
        if str(source or "").strip()
    }
    aliases: dict[str, list[str]] = {}
    for item in citation_candidate_items(prediction):
        runtime_ids = [
            str(item.get(key) or "").strip()
            for key in ("source_id", "document_id", "file_id", "runtime_source_id")
            if str(item.get(key) or "").strip()
        ]
        explicit = [
            str(value or "").strip().split("#", 1)[0]
            for value in (
                *list(item.get("source_aliases") or []),
                *list(item.get("source_backrefs") or []),
            )
            if str(value or "").strip()
        ]
        matched = [value for value in explicit if value in canonical_ids]
        for runtime_id in runtime_ids:
            values = aliases.setdefault(runtime_id, [])
            values.extend(value for value in matched if value not in values)
    return {key: tuple(values) for key, values in aliases.items()}


def canonical_source_backrefs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for source in item.get("source_backrefs") or []:
        value = str(source or "").strip()
        if value and not source_ref_uses_uuid_like_source(value):
            refs.append(value)
    return refs


def terminal_commit_citations(
    prediction: dict[str, Any],
    *,
    span: str,
) -> list[dict[str, str]]:
    candidates = citation_candidate_items(prediction)
    aliases = unambiguous_evidence_alias_lookup(candidates)
    canonical_sources = canonical_source_refs(prediction)
    commits = [
        prediction.get("terminal_semantic_commit"),
        prediction.get("engine_terminal_commit"),
        (
            prediction.get("engine_terminal_state", {}).get("terminal_semantic_commit")
            if isinstance(prediction.get("engine_terminal_state"), dict)
            else None
        ),
    ]
    citations: list[dict[str, str]] = []
    for commit in commits:
        if not isinstance(commit, dict):
            continue
        for value in commit.get("citations") or []:
            reference = str(value or "").strip()
            item = aliases.get(reference)
            citation = (
                citation_from_item(
                    item,
                    span=span,
                    canonical_sources=canonical_sources,
                    source_backrefs=canonical_source_backrefs(item),
                    evidence_identity=reference,
                )
                if item is not None
                else _citation_from_terminal_ref(reference, span=span)
            )
            if citation:
                citations.append(citation)
    return _unique_citations(citations)


def record_frozen_citation_trace(
    prediction: dict[str, Any],
    trace: dict[str, Any],
) -> None:
    for metadata in _citation_metadata_targets(prediction):
        metadata["frozen_citation_projection_trace"] = dict(trace)


def set_citation_projection_source(prediction: dict[str, Any], source: str) -> None:
    for metadata in _citation_metadata_targets(prediction):
        metadata["citation_projection_source"] = source


def citation_projection_source(prediction: dict[str, Any]) -> str:
    for metadata in _citation_metadata_targets(prediction):
        source = str(metadata.get("citation_projection_source") or "").strip()
        if source:
            return source
    return "explicit_citations"


def _citation_from_terminal_ref(value: Any, *, span: str) -> dict[str, str]:
    reference = str(value or "").strip()
    kind = reference.split(":", 1)[0].lower()
    if kind in {"cell", "span", "element", "chunk", "evidence"}:
        return {"kind": kind, "evidence_id": reference, "span": str(span or "")}
    return citation_from_source_ref(reference, span=span)


def _citation_metadata_targets(
    prediction: dict[str, Any],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict) and isinstance(
        evidence_bundle.get("metadata"), dict
    ):
        targets.append(evidence_bundle["metadata"])
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        targets.append(evidence_metadata)
    return targets


def _unique_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for citation in citations:
        key = (
            str(citation.get("kind") or ""),
            str(citation.get("source_id") or ""),
            str(citation.get("page_label") or ""),
            str(citation.get("evidence_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(citation)
    return output
