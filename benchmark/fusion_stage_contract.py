from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.fusion_stage import FUSION_STAGE_CONTRACT, FUSION_STAGE_STATES

_EXPECTED_CANDIDATE_STAGE = {
    "executed": "post_fusion",
    "passthrough": "fusion_passthrough",
    "not_executed": "fusion_not_executed",
}


def fusion_stage_audit(
    prediction: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate the producer snapshot at the fusion/ranking boundary."""

    metadata = _metadata(prediction)
    ranking = _mapping(metadata.get("ranking_trace"))
    marker = str(ranking.get("fusion_stage_contract_id") or "")
    if not marker:
        return {
            "contract_id": FUSION_STAGE_CONTRACT,
            "applicable": False,
            "status": "not_applicable",
            "declared_contract_id": "",
            "violations": [],
        }, []
    return _audit_declared_stage(prediction, metadata, ranking, marker)


def _audit_declared_stage(
    prediction: Mapping[str, Any],
    metadata: Mapping[str, Any],
    ranking: Mapping[str, Any],
    marker: str,
) -> tuple[dict[str, Any], list[str]]:
    snapshot = _mapping(metadata.get("fusion_stage_snapshot"))
    ranking_snapshot = _mapping(ranking.get("fusion_stage_snapshot"))
    candidate_stage = str(ranking.get("candidate_stage") or "")
    violations: list[str] = []
    if marker != FUSION_STAGE_CONTRACT:
        violations.append("fusion_stage_contract_marker_mismatch")
    if not snapshot:
        violations.append("fusion_stage_snapshot_missing")
        if candidate_stage == "post_fusion" and not _records(
            metadata.get("fused_evidence")
        ):
            violations.append("post_fusion_output_missing")
        return (
            _audit_summary(
                prediction,
                snapshot=snapshot,
                ranking=ranking,
                violations=violations,
                contract_marker=marker,
            ),
            violations,
        )
    if not ranking_snapshot:
        violations.append("fusion_stage_ranking_snapshot_missing")
    elif ranking_snapshot != snapshot:
        violations.append("fusion_stage_snapshot_divergence")
    contract_id = str(snapshot.get("contract_id") or "")
    state = str(snapshot.get("state") or "")
    expected_stage = _EXPECTED_CANDIDATE_STAGE.get(state, "")
    if contract_id != FUSION_STAGE_CONTRACT:
        violations.append("fusion_stage_contract_mismatch")
    if state not in FUSION_STAGE_STATES:
        violations.append("fusion_stage_state_invalid")
    if expected_stage and candidate_stage != expected_stage:
        violations.append("fusion_stage_ranking_stage_mismatch")
    if not str(snapshot.get("route") or ""):
        violations.append("fusion_stage_route_missing")
    if snapshot.get("fusion_trace_present") is not (state == "executed"):
        violations.append("fusion_stage_trace_presence_mismatch")
    violations.extend(_audit_stage_records(metadata, snapshot, state))
    return (
        _audit_summary(
            prediction,
            snapshot=snapshot,
            ranking=ranking,
            violations=violations,
            contract_marker=marker,
        ),
        violations,
    )


def _audit_stage_records(
    metadata: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    state: str,
) -> list[str]:
    violations: list[str] = []
    records = {
        "canonical": _records(metadata.get("canonical_candidate_evidence")),
        "ranked": _records(metadata.get("candidate_ranked_evidence")),
        "fused": _records(metadata.get("fused_evidence")),
    }
    identities: dict[str, list[str]] = {}
    for label, values in records.items():
        identities[label], error = _identity_keys(values)
        if error:
            violations.append(f"fusion_stage_{label}_identity_invalid")
    if _non_negative_int(snapshot.get("input_count")) != len(records["canonical"]):
        violations.append("fusion_stage_input_count_mismatch")
    if _non_negative_int(snapshot.get("output_count")) != len(records["ranked"]):
        violations.append("fusion_stage_output_count_mismatch")
    if list(snapshot.get("input_identities") or []) != identities["canonical"]:
        violations.append("fusion_stage_input_identity_mismatch")
    if list(snapshot.get("output_identities") or []) != identities["ranked"]:
        violations.append("fusion_stage_output_identity_mismatch")
    if identities["fused"] != identities["ranked"]:
        violations.append("fusion_stage_fused_output_mismatch")
    if state == "executed":
        violations.extend(_audit_executed_state(metadata, identities))
    elif state == "passthrough":
        violations.extend(_audit_passthrough_state(snapshot, metadata, identities))
    elif state == "not_executed":
        if records["ranked"] or records["fused"]:
            violations.append("fusion_stage_not_executed_has_output")
        if isinstance(metadata.get("hybrid_fusion_trace"), dict):
            violations.append("fusion_stage_not_executed_has_execution_trace")
    return violations


def _audit_executed_state(
    metadata: Mapping[str, Any], identities: Mapping[str, list[str]]
) -> list[str]:
    violations: list[str] = []
    if not isinstance(metadata.get("hybrid_fusion_trace"), dict):
        violations.append("fusion_stage_execution_trace_missing")
    ranked_ids = identities["ranked"]
    if len(ranked_ids) != len(set(ranked_ids)):
        violations.append("fusion_stage_output_identity_duplicate")
    if not set(ranked_ids) <= set(identities["canonical"]):
        violations.append("fusion_stage_output_not_from_input")
    return violations


def _audit_passthrough_state(
    snapshot: Mapping[str, Any],
    metadata: Mapping[str, Any],
    identities: Mapping[str, list[str]],
) -> list[str]:
    violations: list[str] = []
    if isinstance(metadata.get("hybrid_fusion_trace"), dict):
        violations.append("fusion_stage_passthrough_has_execution_trace")
    if not bool(snapshot.get("identity_preserved")):
        violations.append("fusion_stage_passthrough_identity_not_preserved")
    if identities["canonical"] != identities["ranked"]:
        violations.append("fusion_stage_passthrough_changed_candidates")
    return violations


def _audit_summary(
    prediction: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    ranking: Mapping[str, Any],
    violations: list[str],
    contract_marker: str,
) -> dict[str, Any]:
    return {
        "contract_id": FUSION_STAGE_CONTRACT,
        "applicable": True,
        "status": "passed" if not violations else "failed",
        "declared_contract_id": contract_marker,
        "example_id": str(prediction.get("example_id") or ""),
        "route": str(snapshot.get("route") or ""),
        "state": str(snapshot.get("state") or ""),
        "candidate_stage": str(ranking.get("candidate_stage") or ""),
        "input_count": snapshot.get("input_count"),
        "output_count": snapshot.get("output_count"),
        "violations": list(violations),
    }


def _metadata(prediction: Mapping[str, Any]) -> dict[str, Any]:
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, Mapping):
        return dict(metadata)
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, Mapping) and isinstance(bundle.get("metadata"), Mapping):
        return dict(bundle["metadata"])
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _identity_keys(records: list[dict[str, Any]]) -> tuple[list[str], str]:
    identities: list[str] = []
    try:
        for item in records:
            identities.append(identity_of(item).key)
    except (TypeError, ValueError, KeyError) as exc:
        return identities, str(exc)
    return identities, ""


def _non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return -1
    return parsed if parsed >= 0 else -1
