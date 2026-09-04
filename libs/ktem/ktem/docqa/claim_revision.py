from __future__ import annotations

from typing import Any, Callable

from .controller import RetrieveDecision, VerifyDecision
from .evidence import EvidenceBundle

VerifyFn = Callable[
    [Any, RetrieveDecision, EvidenceBundle, str],
    VerifyDecision,
]


def revise_to_supported_claims(
    request: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    verify_decision: VerifyDecision,
    *,
    verify: VerifyFn,
) -> tuple[str, VerifyDecision, dict[str, Any] | None]:
    unsupported = set(verify_decision.unsupported_claims)
    supported = [claim for claim in verify_decision.claims if claim not in unsupported]
    if not supported or len(supported) == len(verify_decision.claims):
        return answer, verify_decision, None
    revised_answer = " ".join(supported)
    revised_verification = verify(
        request,
        retrieve_decision,
        bundle,
        revised_answer,
    )
    return (
        revised_answer,
        revised_verification,
        {
            "stage": "claim_level_revision",
            "kept_claim_count": len(revised_verification.claims),
        },
    )
