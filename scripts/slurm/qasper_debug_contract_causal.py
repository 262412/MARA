from __future__ import annotations

from typing import Any

from benchmark.qasper_candidate_input_state import candidate_input_state_observation
from benchmark.qasper_causal_evidence_chain import qasper_causal_evidence_chain
from scripts.slurm.qasper_debug_contract_support import _mapping, terminal_metadata


def causal_evidence_chain_complete(prediction: dict[str, Any]) -> bool:
    metadata = terminal_metadata(prediction)
    chain = qasper_causal_evidence_chain(
        {
            "example_id": prediction.get("example_id"),
            "route": prediction.get("route"),
            "answer_status": prediction.get("answer_status"),
            "terminal_outcome": prediction.get("terminal_outcome"),
            "terminal_semantic_commit": _mapping(
                prediction.get("terminal_semantic_commit")
            ),
            "qasper_annotation_diagnostics": _mapping(
                prediction.get("qasper_annotation_diagnostics")
            ),
            "main_candidate_generator": _mapping(
                metadata.get("qasper_candidate_generation")
            ),
            "candidate_input_state_observation": candidate_input_state_observation(
                metadata
            ),
            "semantic_verifier": _mapping(
                metadata.get("semantic_proposition_verifier")
            ),
            "recovery_transitions": _mapping(
                metadata.get("semantic_proposition_verifier")
            ).get("recovery_transitions", []),
        }
    )
    return chain.get("status") == "complete"
