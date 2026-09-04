from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of

from .alce_answer_grounding import _supported_answer_consistent

BENCHMARK_ADAPTER_AUTHORITY_COMMIT = "benchmark_adapter_authority_commit.v1"


def project_alce_grounding_support(
    prediction: dict[str, Any],
    *,
    final_answer: str,
) -> bool:
    """Project one accepted ALCE grounding result into citation authority."""

    prediction.pop("benchmark_adapter_authority_commit", None)
    trace = _metadata_value(prediction, "alce_answer_grounding")
    if not isinstance(trace, dict):
        return False
    if (
        str(trace.get("status") or "") != "ok"
        or str(trace.get("verdict") or "") != "supported"
        or bool(trace.get("answer_changed"))
    ):
        return False

    expected_answer = str(trace.get("grounded_answer") or "")
    if not expected_answer or not _supported_answer_consistent(
        expected_answer,
        final_answer,
    ):
        return False
    candidate = _resolve_evidence_alias(
        _citation_candidates(prediction),
        str(trace.get("evidence_id") or ""),
    )
    if candidate is None:
        return False
    by_claim = {"alce:grounding": [identity_of(candidate).key]}
    _record_support(
        prediction,
        items=[candidate],
        by_claim=by_claim,
    )
    _record_adapter_authority_commit(
        prediction,
        adapter="alce_grounding",
        semantic_answer=final_answer,
        items=[candidate],
        by_claim=by_claim,
        claim_texts={"alce:grounding": expected_answer},
    )
    return True


def project_ragtruth_claim_support(
    prediction: dict[str, Any],
    *,
    final_answer: str,
) -> bool:
    """Bridge supported RAGTruth claims to unique canonical evidence."""

    prediction.pop("benchmark_adapter_authority_commit", None)
    supported = _metadata_value(prediction, "ragtruth_supported_claim_indices")
    claims = _metadata_value(prediction, "ragtruth_claims")
    if not isinstance(supported, list) or not isinstance(claims, list):
        return False
    if not supported or not claims:
        return False
    try:
        supported_indices = [int(index) for index in supported]
    except (TypeError, ValueError):
        return False
    if any(index < 0 or index >= len(claims) for index in supported_indices):
        return False
    if any(
        not isinstance(claims[index], str) or not claims[index].strip()
        for index in supported_indices
    ):
        return False

    # Emitted indices are an output of the hallucination contract, never a
    # source of citation authority. A contradictory overlap is fail-closed.
    emitted = _metadata_value(prediction, "ragtruth_emitted_claim_indices")
    if _integer_indices(emitted) & set(supported_indices):
        return False

    source_item = _resolve_evidence_alias(
        _citation_candidates(prediction),
        str(_metadata_value(prediction, "ragtruth_source_evidence_id") or ""),
    )
    if source_item is None:
        return False
    source_identity = identity_of(source_item).key
    by_claim = {
        f"ragtruth:claim:{index}": [source_identity]
        for index in dict.fromkeys(supported_indices)
    }
    _record_support(
        prediction,
        items=[source_item],
        by_claim=by_claim,
    )
    _record_adapter_authority_commit(
        prediction,
        adapter="ragtruth_claim_verifier",
        semantic_answer=final_answer,
        items=[source_item],
        by_claim=by_claim,
        claim_texts={
            f"ragtruth:claim:{index}": str(claims[index]).strip()
            for index in dict.fromkeys(supported_indices)
        },
    )
    return True


def validated_adapter_authority_commit(
    prediction: dict[str, Any],
    *,
    runtime_answer: str,
) -> dict[str, Any] | None:
    commit = prediction.get("benchmark_adapter_authority_commit")
    if not isinstance(commit, dict) or commit.get("contract_id") != (
        BENCHMARK_ADAPTER_AUTHORITY_COMMIT
    ):
        return None
    unsigned = {key: value for key, value in commit.items() if key != "projection_hash"}
    if str(commit.get("projection_hash") or "") != _payload_hash(unsigned):
        return None
    if commit.get("status") != "supported" or commit.get("state_version") != 1:
        return None
    semantic_answer = str(commit.get("semantic_answer") or "").strip()
    adapter = str(commit.get("adapter") or "").strip()
    if not semantic_answer or not _adapter_answer_matches(
        adapter,
        semantic_answer,
        runtime_answer,
    ):
        return None
    evidence = [
        dict(item)
        for item in commit.get("authoritative_evidence") or []
        if isinstance(item, dict)
    ]
    if not evidence or not _commit_evidence_is_selected(prediction, evidence):
        return None
    try:
        evidence_ids = {identity_of(item).key for item in evidence}
    except (TypeError, ValueError):
        return None
    verified_citations = {
        str(value).strip()
        for value in commit.get("verified_citations") or []
        if str(value).strip()
    }
    if verified_citations != evidence_ids:
        return None
    claim_results = commit.get("claim_results")
    if not isinstance(claim_results, list) or not claim_results:
        return None
    claimed_ids: set[str] = set()
    claim_ids: set[str] = set()
    for result in claim_results:
        if not isinstance(result, dict) or result.get("status") != "supported":
            return None
        if (
            not str(result.get("claim_id") or "").strip()
            or not str(result.get("claim") or "").strip()
        ):
            return None
        claim_id = str(result["claim_id"]).strip()
        if claim_id in claim_ids:
            return None
        claim_ids.add(claim_id)
        supporting = {
            str(value).strip()
            for value in result.get("supporting_evidence_ids") or []
            if str(value).strip()
        }
        if not supporting or not supporting <= evidence_ids:
            return None
        claimed_ids.update(supporting)
    if claimed_ids != evidence_ids:
        return None
    return deepcopy(commit)


def _metadata_value(prediction: dict[str, Any], key: str) -> Any:
    values = [
        metadata[key] for metadata in _metadata_sources(prediction) if key in metadata
    ]
    if not values or any(value != values[0] for value in values[1:]):
        return None
    return values[0]


def _metadata_sources(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        metadata = evidence_bundle.get("metadata")
        if isinstance(metadata, dict):
            sources.append(metadata)
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        sources.append(evidence_metadata)
    return sources


def _citation_candidates(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
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
            "selected_evidence",
            "generation_context_evidence",
            "evidence",
        ):
            items.extend(
                item
                for item in evidence_metadata.get(key) or []
                if isinstance(item, dict)
            )
    items.extend(
        item
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    )
    return items


def _resolve_evidence_alias(
    candidates: list[dict[str, Any]],
    evidence_id: str,
) -> dict[str, Any] | None:
    target = str(evidence_id or "").strip()
    if not target:
        return None
    direct = unambiguous_evidence_alias_lookup(candidates).get(target)
    if direct is not None:
        return direct
    by_identity: dict[str, dict[str, Any]] = {}
    for item in candidates:
        if not any(
            str(item.get(key) or "").strip() == target
            for key in (
                "evidence_id",
                "canonical_id",
                "runtime_identity",
                "evaluation_identity",
            )
        ):
            continue
        try:
            by_identity[identity_of(item).key] = item
        except (TypeError, ValueError):
            continue
    return next(iter(by_identity.values())) if len(by_identity) == 1 else None


def _record_support(
    prediction: dict[str, Any],
    *,
    items: list[dict[str, Any]],
    by_claim: dict[str, list[str]],
) -> None:
    targets = _metadata_sources(prediction)
    if not targets:
        targets = [prediction.setdefault("evidence_metadata", {})]
    for metadata in targets:
        metadata["verified_claim_support_evidence"] = list(items)
        metadata["verified_claim_support_by_claim"] = dict(by_claim)


def _record_adapter_authority_commit(
    prediction: dict[str, Any],
    *,
    adapter: str,
    semantic_answer: str,
    items: list[dict[str, Any]],
    by_claim: dict[str, list[str]],
    claim_texts: dict[str, str],
) -> None:
    claim_results = [
        {
            "claim_id": claim_id,
            "claim": claim_texts[claim_id],
            "status": "supported",
            "supporting_evidence_ids": list(evidence_ids),
        }
        for claim_id, evidence_ids in by_claim.items()
    ]
    evidence_ids = list(
        dict.fromkeys(
            evidence_id for values in by_claim.values() for evidence_id in values
        )
    )
    unsigned = {
        "contract_id": BENCHMARK_ADAPTER_AUTHORITY_COMMIT,
        "adapter": adapter,
        "semantic_answer": str(semantic_answer or "").strip(),
        "status": "supported",
        "authoritative_evidence": [deepcopy(item) for item in items],
        "claim_results": claim_results,
        "verified_citations": evidence_ids,
        "state_version": 1,
    }
    prediction["benchmark_adapter_authority_commit"] = {
        **unsigned,
        "projection_hash": _payload_hash(unsigned),
    }


def _adapter_answer_matches(
    adapter: str,
    expected: str,
    runtime_answer: str,
) -> bool:
    if adapter == "alce_grounding":
        return _supported_answer_consistent(expected, runtime_answer)
    if adapter == "ragtruth_claim_verifier":
        return " ".join(expected.split()) == " ".join(str(runtime_answer or "").split())
    return False


def _commit_evidence_is_selected(
    prediction: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> bool:
    candidates = _citation_candidates(prediction)
    for committed in evidence:
        try:
            identity = identity_of(committed).key
        except (TypeError, ValueError):
            return False
        exact_match = False
        for candidate in candidates:
            try:
                candidate_identity = identity_of(candidate).key
            except (TypeError, ValueError):
                continue
            if candidate_identity == identity and candidate == committed:
                exact_match = True
                break
        if not exact_match:
            return False
    return True


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _integer_indices(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    try:
        return {int(index) for index in value}
    except (TypeError, ValueError):
        return set()
