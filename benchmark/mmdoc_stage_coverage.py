from __future__ import annotations

from typing import Any

from .mmdoc_locator_crosswalk import (
    _crosswalk_from_prediction,
    _evidence_canonical_ids,
    _is_audited_crosswalk,
    _is_mmdoc_prediction,
    _mapping_identity_ids,
    _mapping_matches_gold,
    _records,
)


def audited_mmdoc_stage_coverage(
    prediction: dict[str, Any],
    stage_items: list[dict[str, Any]],
) -> float | None:
    """Score a finalized stage through exact mapped and verified identities."""

    dataset_values = (
        prediction.get("dataset_name"),
        prediction.get("dataset_family"),
        prediction.get("verification_domain"),
    )
    if any(
        value not in (None, "") for value in dataset_values
    ) and not _is_mmdoc_prediction(prediction, None):
        return None
    crosswalk = _crosswalk_from_prediction(prediction)
    if not isinstance(crosswalk, dict) or not _is_audited_crosswalk(crosswalk):
        return None
    gold_records = _records(prediction.get("gold_evidence"))
    if not gold_records:
        return 0.0

    metadata = prediction.get("evidence_metadata")
    if not isinstance(metadata, dict):
        return 0.0
    verified_ids = {
        identity
        for key in ("verified_evidence", "verified_claim_support_evidence")
        for item in _records(metadata.get(key))
        for identity in _evidence_canonical_ids(item)
    }
    stage_ids = set().union(*(_evidence_canonical_ids(item) for item in stage_items))
    mappings = _records(crosswalk.get("mappings"))
    matched = 0
    for gold in gold_records:
        mapped_ids = set().union(
            *(
                _mapping_identity_ids(mapping)
                for mapping in mappings
                if _mapping_matches_gold(mapping, gold)
            )
        )
        if mapped_ids & verified_ids & stage_ids:
            matched += 1
    return matched / len(gold_records)
