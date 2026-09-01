from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest


def candidate_input_state_observation(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Compare the frozen candidate input rank with the later bundle state."""

    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    source = _mapping(pack.get("source_packing_observation"))
    snapshot = _mapping(source.get("source_input_snapshot"))
    stage_ranked = _ranked_rows(snapshot.get("ranked_evidence"))
    terminal_ranked = _terminal_ranked_rows(metadata.get("candidate_ranked_evidence"))
    stage_ids = [str(row.get("canonical_id") or "") for row in stage_ranked]
    terminal_ids = [str(row.get("canonical_id") or "") for row in terminal_ranked]
    first_divergence = _first_divergence(stage_ids, terminal_ids)
    payload = {
        "contract_id": "qasper_candidate_input_state_observation.v1",
        "complete": bool(
            snapshot.get("contract_id") == "semantic_source_input_snapshot.v1"
            and snapshot.get("complete") is True
            and stage_ranked
        ),
        "status": "preserved" if stage_ids == terminal_ids else "drifted",
        "stage_ranked_evidence_present": snapshot.get("ranked_evidence_present")
        is True,
        "stage_ranked_evidence_count": len(stage_ranked),
        "stage_ranked_evidence_digest": canonical_digest(stage_ranked),
        "stage_ranked_evidence": stage_ranked,
        "terminal_ranked_evidence_present": "candidate_ranked_evidence" in metadata,
        "terminal_ranked_evidence_count": len(terminal_ranked),
        "terminal_ranked_evidence_digest": canonical_digest(terminal_ranked),
        "terminal_ranked_evidence": terminal_ranked,
        "first_divergence": first_divergence,
        "added_after_candidate": _ordered_difference(terminal_ids, stage_ids),
        "removed_after_candidate": _ordered_difference(stage_ids, terminal_ids),
        "source_input_snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
    }
    payload["observation_digest"] = canonical_digest(payload)
    return payload


def _ranked_rows(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else []
    return [
        {
            "ranked_position": row.get("ranked_position"),
            "canonical_id": str(row.get("canonical_id") or ""),
        }
        for row in values
        if isinstance(row, Mapping)
    ]


def _terminal_ranked_rows(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else []
    return [
        {
            "ranked_position": index,
            "canonical_id": (
                str(row.get("canonical_id") or "") if isinstance(row, Mapping) else ""
            ),
        }
        for index, row in enumerate(values)
    ]


def _first_divergence(stage_ids: list[str], terminal_ids: list[str]) -> dict[str, Any]:
    for index in range(max(len(stage_ids), len(terminal_ids))):
        stage_id = stage_ids[index] if index < len(stage_ids) else ""
        terminal_id = terminal_ids[index] if index < len(terminal_ids) else ""
        if stage_id != terminal_id:
            return {
                "ranked_position": index,
                "stage_canonical_id": stage_id,
                "terminal_canonical_id": terminal_id,
            }
    return {}


def _ordered_difference(values: list[str], baseline: list[str]) -> list[str]:
    baseline_values = set(baseline)
    return list(
        dict.fromkeys(value for value in values if value not in baseline_values)
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
