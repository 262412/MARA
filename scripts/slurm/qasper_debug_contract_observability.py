from __future__ import annotations

from typing import Any

from scripts.slurm.qasper_debug_contract_identity import _raw_candidate_identity_valid
from scripts.slurm.qasper_debug_contract_semantic_pack import (
    canonical_semantic_pack_alignment_valid,
)
from scripts.slurm.qasper_debug_contract_support import (
    _candidate_bound_auditor_attempt_observed,
    _candidate_bound_auditor_passed,
    _candidate_proposition_binding_complete,
    _empty_coverage_counts,
    _failed_auditor_safe_abstention,
    _input_output_digests_complete,
    _live_models_observed,
    _mapping,
    _semantic_debug_complete,
    _transaction_identity_complete,
    _verifier_observed,
    claim_aggregation_complete,
    terminal_metadata,
)


def qasper_debug_observability_coverage(
    predictions: list[dict[str, Any]],
    *,
    require_auditor: bool = True,
) -> dict[str, Any]:
    fields = _observability_counts(predictions)
    total = len(predictions)
    auditor_outcome_coverage = (
        fields["candidate_verifier_audit"] + fields["auditor_failed_safe_abstention"]
    )
    required_fields = {
        key: value
        for key, value in fields.items()
        if key
        not in {
            "candidate_verifier_audit",
            "auditor_failed_safe_abstention",
            "auditor_attempt_observed",
        }
    }
    if require_auditor:
        required_fields["auditor_attempt_observed"] = fields["auditor_attempt_observed"]
    complete = bool(
        total
        and all(value == total for value in required_fields.values())
        and (auditor_outcome_coverage == total if require_auditor else True)
    )
    return {
        "contract_id": "qasper_e2e_observability_coverage.v1",
        "prediction_count": total,
        "covered_counts": fields,
        "auditor_outcome_coverage": auditor_outcome_coverage,
        "auditor_required": require_auditor,
        "complete": complete,
    }


def _observability_counts(predictions: list[dict[str, Any]]) -> dict[str, int]:
    fields = _empty_coverage_counts()
    for prediction in predictions:
        metadata = terminal_metadata(prediction)
        generator = _mapping(metadata.get("qasper_candidate_generation"))
        verifier = _mapping(metadata.get("semantic_proposition_verifier"))
        fields["generator_trace"] += int(bool(generator))
        fields["raw_response"] += int("raw_response" in generator)
        fields["raw_candidate_identity"] += int(
            _raw_candidate_identity_valid(generator, verifier)
        )
        fields["finish_reason"] += int(bool(generator.get("finish_reason")))
        fields["typed_candidate_transform"] += int(
            bool(generator.get("transformation_stages"))
        )
        fields["proposition_slot_binding"] += int(
            _candidate_proposition_binding_complete(generator)
        )
        fields["claim_aggregation_before_after"] += int(
            claim_aggregation_complete(prediction)
        )
        fields["per_annotation_scores"] += int(
            bool(prediction.get("qasper_annotation_scores"))
        )
        fields["transaction_attempt_identity"] += int(
            _transaction_identity_complete(generator, verifier)
        )
        fields["effective_seed"] += int(
            generator.get("effective_seed") is not None
            and generator.get("effective_seed") == verifier.get("effective_seed")
        )
        fields["input_output_digest"] += int(
            _input_output_digests_complete(generator, verifier)
        )
        fields["verifier_observed"] += int(_verifier_observed(verifier))
        fields["auditor_attempt_observed"] += int(
            _candidate_bound_auditor_attempt_observed(verifier)
        )
        fields["candidate_verifier_audit"] += int(
            _candidate_bound_auditor_passed(verifier)
        )
        fields["auditor_failed_safe_abstention"] += int(
            _failed_auditor_safe_abstention(verifier, prediction)
        )
        fields["semantic_verifier_debug"] += int(_semantic_debug_complete(verifier))
        fields["canonical_semantic_pack_alignment"] += int(
            canonical_semantic_pack_alignment_valid(prediction)
        )
        fields["live_model"] += int(_live_models_observed(generator, verifier))
    return fields
