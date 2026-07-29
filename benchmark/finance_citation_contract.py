from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .calculation_citation_projection import (
    calculation_citation_items,
    record_calculation_stage_evidence,
)


def record_execution_operand_evidence(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
    canonical_sources: list[str],
) -> None:
    record_calculation_stage_evidence(
        prediction,
        calculation_citation_items(prediction, candidates),
        canonical_sources=canonical_sources,
    )


def typed_calculation_is_verified(prediction: dict[str, Any]) -> bool:
    for container in _trace_containers(prediction):
        trace = dict(container.get("finance_numeric_trace") or {})
        verification = dict(trace.get("calculation_verification") or {})
        execution = dict(trace.get("calculation_execution") or {})
        if verification.get("valid") and execution.get("status") == "ok":
            return True
    return False


def record_verified_claim_support(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
) -> None:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        identity = identity_of(item).key
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(item)
    for metadata in citation_metadata_targets(prediction):
        metadata["verified_claim_support_evidence"] = list(unique)


def clear_answer_citation_state(prediction: dict[str, Any]) -> None:
    prediction["structured_citations"] = []
    prediction["predicted_citations"] = []
    for metadata in citation_metadata_targets(prediction):
        metadata["verified_claim_support_evidence"] = []
        metadata["emitted_citation_evidence"] = []
        metadata["cited_evidence"] = []


def citation_metadata_targets(
    prediction: dict[str, Any],
) -> list[dict[str, Any]]:
    metadata = prediction.get("evidence_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        prediction["evidence_metadata"] = metadata
    targets = [metadata]
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict) and isinstance(bundle.get("metadata"), dict):
        targets.append(bundle["metadata"])
    return targets


def _trace_containers(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    containers = []
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        containers.append(metadata)
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        bundle_metadata = bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            containers.append(bundle_metadata)
        containers.append(bundle)
    return containers
