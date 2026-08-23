from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.candidate_verification_policy import CANDIDATE_VERIFICATION_CONTRACT


def candidate_bound_response(
    response: dict[str, Any],
    candidate: str,
) -> dict[str, Any]:
    bounded = deepcopy(response)
    verdict = str(bounded.get("verdict") or "")
    if candidate == "unanswerable":
        status = "supported" if verdict == "insufficient_evidence" else "contradicted"
    elif verdict == candidate:
        status = "supported"
    elif verdict in {"yes", "no"}:
        status = "contradicted"
    else:
        status = "unknown"
    bounded.update(
        candidate_verification_contract=CANDIDATE_VERIFICATION_CONTRACT,
        verifier_input_candidate=candidate,
        candidate_verification_status=status,
        replacement_candidate_allowed=False,
    )
    return bounded
