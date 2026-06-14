from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .claim_filtering import answer_claims, clean_answer_text
from .evidence import EvidenceBundle
from .finance_verification import (
    evidence_text,
    finance_numeric_claim_supported,
    finance_verification_claims,
)


@dataclass(frozen=True)
class VerifyDecision:
    mode: str
    status: str
    reason: str
    action: str = "generate"
    claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    verified_citations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_decision(
    request: Any,
    retrieve_decision: Any,
    evidence_bundle: EvidenceBundle,
    answer: str = "",
) -> VerifyDecision:
    mode = normalize_verification_mode(getattr(request, "verification_mode", None))
    if mode == "off":
        return VerifyDecision(
            mode=mode, status="not_requested", reason="Verification disabled."
        )
    if retrieve_decision.status == "not_required":
        return VerifyDecision(
            mode=mode,
            status="not_required",
            reason="Direct route does not require evidence verification.",
        )
    citations = verified_citations(evidence_bundle)
    if retrieve_decision.status != "good":
        action = "retry" if retrieve_decision.retry else "abstain"
        return VerifyDecision(
            mode=mode,
            status="not_enough_evidence",
            reason=f"{mode.title()} verification requested without sufficient evidence.",
            action=action,
        )

    prompt = str(getattr(request, "prompt", "") or "")
    cleaned_answer = clean_answer_text(answer)
    claims = finance_verification_claims(answer_claims(cleaned_answer), prompt=prompt)
    unsupported = [
        claim
        for claim in claims
        if not claim_supported(
            claim,
            evidence_bundle.items,
            prompt=prompt,
        )
    ]
    if unsupported:
        return VerifyDecision(
            mode=mode,
            status="unsupported",
            reason=f"{mode.title()} verification found unsupported claims.",
            action="revise",
            claims=claims,
            unsupported_claims=unsupported,
            verified_citations=citations,
        )

    return VerifyDecision(
        mode=mode,
        status="supported",
        reason=f"{mode.title()} verification requested; current verifier observed evidence.",
        claims=claims,
        verified_citations=citations,
    )


def normalize_verification_mode(value: Any) -> str:
    mode = str(value or "off").strip().lower()
    return mode if mode in {"off", "light", "strict"} else "off"


def verified_citations(evidence_bundle: EvidenceBundle) -> list[str]:
    citations: list[str] = []
    for item in evidence_bundle.items:
        evidence_id = str(item.get("evidence_id") or "").strip()
        if evidence_id and evidence_id not in citations:
            citations.append(evidence_id)
    return citations


def claim_supported(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str = "",
) -> bool:
    finance_supported = finance_numeric_claim_supported(
        claim,
        evidence_items,
        prompt=prompt,
    )
    if finance_supported is not None:
        return finance_supported

    claim_tokens = meaningful_tokens(claim)
    if not claim_tokens:
        return True
    evidence_tokens = meaningful_tokens(evidence_text(evidence_items))
    return len(claim_tokens & evidence_tokens) >= min(2, len(claim_tokens))


def meaningful_tokens(value: str) -> set[str]:
    stop_words = {
        "about",
        "after",
        "before",
        "does",
        "from",
        "have",
        "that",
        "this",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 3 and token not in stop_words
    }
