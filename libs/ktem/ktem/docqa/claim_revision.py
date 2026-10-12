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
    typed_authority = verify_decision.typed_authority
    typed_authority = typed_authority if isinstance(typed_authority, dict) else {}
    revision_candidate = str(typed_authority.get("revision_candidate") or "").strip()
    if revision_candidate and revision_candidate != str(answer or "").strip():
        revised_verification = verify(
            request,
            retrieve_decision,
            bundle,
            revision_candidate,
        )
        return (
            revision_candidate,
            revised_verification,
            {
                "stage": "claim_level_revision",
                "kept_claim_count": len(revised_verification.claims),
            },
        )
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
