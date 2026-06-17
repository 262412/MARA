from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .claim_filtering import answer_claims
from .domain_verifiers import (
    domain_claim_supported,
    domain_verification_claims,
    normalize_verification_domain,
)
from .evidence import EvidenceBundle
from .evidence_text import evidence_text, extract_final_answer_text


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
            reason=(
                f"{mode.title()} verification requested without sufficient evidence."
            ),
            action=action,
        )

    prompt = str(getattr(request, "prompt", "") or "")
    domain = normalize_verification_domain(
        getattr(request, "verification_domain", None)
    )
    cleaned_answer = extract_final_answer_text(answer)
    claims = domain_verification_claims(
        domain,
        answer_claims(cleaned_answer),
        prompt=prompt,
    )
    unsupported = [
        claim
        for claim in claims
        if not claim_supported(
            claim,
            evidence_bundle.items,
            prompt=prompt,
            domain=domain,
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
        reason=(
            f"{mode.title()} verification requested; current verifier observed "
            "evidence."
        ),
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
    domain: str = "",
) -> bool:
    domain_supported = domain_claim_supported(
        domain,
        claim,
        evidence_items,
        prompt=prompt,
    )
    if domain_supported is not None:
        return domain_supported

    claim_tokens = meaningful_tokens(claim)
    if not claim_tokens:
        return True
    evidence_tokens = meaningful_tokens(evidence_text(evidence_items))
    if _short_evidence_supports_claim(evidence_tokens, claim_tokens):
        return True
    overlap = claim_tokens & evidence_tokens
    if len(overlap) >= min(2, len(claim_tokens)):
        return True
    return _source_summary_supports_claim(prompt, overlap, evidence_tokens)


def _short_evidence_supports_claim(
    evidence_tokens: set[str],
    claim_tokens: set[str],
) -> bool:
    if not evidence_tokens or len(evidence_tokens) > 2:
        return False
    return evidence_tokens <= claim_tokens


def _source_summary_supports_claim(
    prompt: str,
    overlap: set[str],
    evidence_tokens: set[str],
) -> bool:
    if not _is_source_summary_prompt(prompt) or len(evidence_tokens) < 20:
        return False
    return bool(overlap - _SUMMARY_GENERIC_TOKENS)


def _is_source_summary_prompt(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return any(
        marker in lowered
        for marker in (
            "summarize",
            "summarise",
            "summary",
            "overview",
            "based only on the provided",
            "based only on the structured data",
        )
    )


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
        normalized
        for token in re.findall(r"[a-zA-Z0-9]+", _token_text(value).lower())
        if (normalized := _normalize_token(token))
        and len(normalized) > 3
        and normalized not in stop_words
    }


def _token_text(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return text.replace("_", " ").replace("-", " ")


def _normalize_token(token: str) -> str:
    value = str(token or "").lower()
    if len(value) > 4 and value.endswith("ies"):
        return f"{value[:-3]}y"
    if len(value) > 4 and value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


_SUMMARY_GENERIC_TOKENS = {
    "article",
    "business",
    "customer",
    "experience",
    "include",
    "including",
    "overview",
    "overall",
    "provide",
    "review",
    "source",
    "summary",
}
