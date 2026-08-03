from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .boolean_claim_verification import boolean_evidence_assessment
from .calculation_claim_verification import calculation_claim_result
from .calculation_evidence_identity import calculation_evidence_lookup
from .claim_clauses import split_claim_clauses
from .claim_filtering import answer_claims
from .claim_support import (
    claim_supported,
    item_supports_claim,
    text_contradicts_claim,
    unsupported_confidence,
    unsupported_threshold,
)
from .domain_verifiers import (
    domain_claim_supported,
    domain_verification_claims,
    normalize_verification_domain,
)
from .evidence import EvidenceBundle
from .evidence_identity import identity_of
from .evidence_text import evidence_text, extract_final_answer_text
from .query_planning import request_planning_question
from .verification_evidence_mapping import (
    claim_support_identities_by_claim,
    missing_verification_slots,
    verification_slots,
)


@dataclass(frozen=True)
class VerifiedClaim:
    claim_id: str
    claim: str
    status: str
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supporting_evidence_ids"] = list(self.supporting_evidence_ids)
        payload["contradicting_evidence_ids"] = list(self.contradicting_evidence_ids)
        return payload


@dataclass(frozen=True)
class VerifyDecision:
    mode: str
    status: str
    reason: str
    action: str = "generate"
    claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    unknown_claims: list[str] = field(default_factory=list)
    verified_citations: list[str] = field(default_factory=list)
    claim_results: list[dict[str, Any]] = field(default_factory=list)

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
            mode=mode,
            status="not_requested",
            reason="Verification disabled.",
        )
    if retrieve_decision.status == "not_required":
        return VerifyDecision(
            mode=mode,
            status="not_required",
            reason="Direct route does not require evidence verification.",
        )
    missing_slots = missing_verification_slots(request)
    if missing_slots:
        action = "retry" if retrieve_decision.retry else "abstain"
        return VerifyDecision(
            mode=mode,
            status="not_enough_evidence",
            reason=(
                "Verification-required evidence slots are missing: "
                + ", ".join(missing_slots)
            ),
            action=action,
        )
    prompt, domain, claims = _verification_context(request, answer)
    if retrieve_decision.status != "good" and not _can_verify_available_evidence(
        evidence_bundle,
        claims,
    ):
        action = "retry" if retrieve_decision.retry else "abstain"
        return VerifyDecision(
            mode=mode,
            status="not_enough_evidence",
            reason=f"{mode.title()} verification requested without sufficient evidence.",
            action=action,
        )
    calculation_claims = split_claim_clauses(claims) if domain == "finance" else claims
    typed_calculation = calculation_claim_result(
        evidence_bundle,
        answer,
        calculation_claims,
        domain=domain,
        prompt=prompt,
    )
    if typed_calculation is not None:
        claims = calculation_claims
        results = _calculation_verification_results(
            typed_calculation,
            claims,
            evidence_bundle.items,
            prompt=prompt,
            domain=domain,
        )
    else:
        typed_boolean = _boolean_verification(
            prompt,
            answer,
            evidence_bundle.items,
        )
        if typed_boolean is not None:
            claims, results = typed_boolean
        else:
            results = _verify_claims(claims, evidence_bundle.items, prompt, domain)
    decision = _decision_for_claim_results(
        mode,
        retrieve_decision.status,
        claims,
        results,
        evidence_bundle.items,
        prompt=prompt,
        domain=domain,
    )
    return _enforce_verification_slot_support(request, decision)


def _calculation_verification_results(
    typed_calculation: Any,
    claims: list[str],
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
    domain: str,
) -> list[VerifiedClaim]:
    results = []
    typed_result_used = False
    for index, claim in enumerate(claims, start=1):
        if claim == typed_calculation.claim and not typed_result_used:
            typed_result_used = True
            results.append(
                VerifiedClaim(
                    claim_id=f"claim:{index}",
                    claim=claim,
                    status=typed_calculation.status,
                    supporting_evidence_ids=typed_calculation.supporting_evidence_ids,
                    contradicting_evidence_ids=(
                        typed_calculation.contradicting_evidence_ids
                    ),
                )
            )
            continue
        results.append(
            verify_claim(
                claim,
                evidence_items,
                claim_id=f"claim:{index}",
                prompt=prompt,
                domain=domain,
            )
        )
    return results


def normalize_verification_mode(value: Any) -> str:
    mode = str(value or "off").strip().lower()
    return mode if mode in {"off", "light", "strict"} else "off"


def with_verification_evidence(
    bundle: EvidenceBundle,
    decision: VerifyDecision,
    request: Any | None = None,
) -> EvidenceBundle:
    if decision.status not in {"supported", "unsupported", "unknown"}:
        return bundle
    citation_ids = {
        str(citation).strip()
        for citation in decision.verified_citations
        if str(citation).strip()
    }
    lookup = calculation_evidence_lookup(bundle.items)
    verified = []
    seen: set[str] = set()
    for citation_id in citation_ids:
        item = lookup.get(citation_id)
        if item is None:
            continue
        identity = identity_of(item).key
        if identity not in seen:
            seen.add(identity)
            verified.append(item)
    metadata = dict(bundle.metadata)
    metadata["verified_evidence"] = verified
    metadata["verified_claim_support_evidence"] = list(verified)
    metadata["verified_claim_support_by_claim"] = claim_support_identities_by_claim(
        decision.claim_results,
        lookup,
    )
    if request is not None:
        metadata["verification_slot_states"] = _verification_slot_states(
            request,
            {identity_of(item).key for item in verified},
        )
    return EvidenceBundle(route=bundle.route, items=bundle.items, metadata=metadata)


def _verification_slot_states(
    request: Any,
    verified_evidence_ids: set[str],
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for slot in verification_slots(request):
        evidence_ids = list(getattr(slot, "evidence_ids", ()) or ())
        states.append(
            {
                "slot_id": str(getattr(slot, "slot_id", "") or ""),
                "status": (
                    "verified_support"
                    if set(evidence_ids) & verified_evidence_ids
                    else str(getattr(slot, "status", "") or "missing")
                ),
                "evidence_ids": evidence_ids,
            }
        )
    return states


def verified_citations(
    evidence_bundle: EvidenceBundle,
    *,
    claims: list[str] | None = None,
    prompt: str = "",
    domain: str = "",
) -> list[str]:
    if claims is None:
        return []
    citations: list[str] = []
    for claim in claims:
        supporting_items = [
            item
            for item in evidence_bundle.items
            if claim_supported(claim, [item], prompt=prompt, domain=domain)
        ]
        for item in supporting_items:
            evidence_id = identity_of(item).key
            if evidence_id and evidence_id not in citations:
                citations.append(evidence_id)
    return citations


def verify_claim(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    claim_id: str,
    prompt: str = "",
    domain: str = "",
) -> VerifiedClaim:
    domain_supported = domain_claim_supported(
        domain,
        claim,
        evidence_items,
        prompt=prompt,
    )
    if domain_supported is True:
        return VerifiedClaim(
            claim_id=claim_id,
            claim=claim,
            status="supported",
            supporting_evidence_ids=_domain_supporting_identities(
                domain,
                claim,
                evidence_items,
                prompt=prompt,
            ),
        )
    supporting = [
        identity_of(item).key
        for item in evidence_items
        if item_supports_claim(claim, item, prompt=prompt)
    ]
    contradicting = [
        identity_of(item).key
        for item in evidence_items
        if text_contradicts_claim(claim, evidence_text([item]))
    ]
    if supporting and contradicting:
        return VerifiedClaim(
            claim_id=claim_id,
            claim=claim,
            status="conflicting",
            supporting_evidence_ids=tuple(dict.fromkeys(supporting)),
            contradicting_evidence_ids=tuple(dict.fromkeys(contradicting)),
        )
    if supporting:
        return VerifiedClaim(
            claim_id=claim_id,
            claim=claim,
            status="supported",
            supporting_evidence_ids=tuple(dict.fromkeys(supporting)),
            contradicting_evidence_ids=tuple(dict.fromkeys(contradicting)),
        )
    if domain_supported is False and not contradicting:
        contradicting = [identity_of(item).key for item in evidence_items]
    if contradicting:
        return VerifiedClaim(
            claim_id=claim_id,
            claim=claim,
            status="contradicted",
            contradicting_evidence_ids=tuple(dict.fromkeys(contradicting)),
        )
    return VerifiedClaim(claim_id=claim_id, claim=claim, status="unknown")


def _verification_context(
    request: Any,
    answer: str,
) -> tuple[str, str, list[str]]:
    prompt = request_planning_question(request)
    domain = normalize_verification_domain(
        getattr(request, "verification_domain", None)
    )
    claims = domain_verification_claims(
        domain,
        answer_claims(extract_final_answer_text(answer)),
        prompt=prompt,
    )
    return prompt, domain, claims


def _verify_claims(
    claims: list[str],
    evidence_items: list[dict[str, Any]],
    prompt: str,
    domain: str,
) -> list[VerifiedClaim]:
    return [
        verify_claim(
            claim,
            evidence_items,
            claim_id=f"claim:{index}",
            prompt=prompt,
            domain=domain,
        )
        for index, claim in enumerate(claims, start=1)
    ]


def _decision_for_claim_results(
    mode: str,
    retrieve_status: str,
    claims: list[str],
    results: list[VerifiedClaim],
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
    domain: str,
) -> VerifyDecision:
    unsupported, unknown = _unsupported_and_unknown(
        results,
        evidence_items,
        mode=mode,
        prompt=prompt,
        domain=domain,
    )
    citations = list(
        dict.fromkeys(
            evidence_id
            for result in results
            if result.status == "supported"
            for evidence_id in result.supporting_evidence_ids
        )
    )
    serialized = [result.as_dict() for result in results]
    if unsupported:
        return _result_decision(
            mode,
            claims,
            unknown,
            citations,
            serialized,
            status="unsupported",
            reason=f"{mode.title()} verification found unsupported claims.",
            action="revise",
            unsupported_claims=unsupported,
        )
    if unknown:
        supported_core = bool(results and results[0].status == "supported")
        if supported_core:
            return _result_decision(
                mode,
                claims,
                unknown,
                citations,
                serialized,
                status="unsupported",
                reason=(
                    f"{mode.title()} verification supported the core claim but "
                    "found unsupported or conflicting extensions."
                ),
                action="revise",
                unsupported_claims=unknown,
            )
        return _result_decision(
            mode,
            claims,
            unknown,
            citations,
            serialized,
            status="unknown",
            reason=(
                f"{mode.title()} verification could not establish claim-level "
                "support for every claim."
            ),
        )
    return _result_decision(
        mode,
        claims,
        unknown,
        citations,
        serialized,
        status="supported",
        reason=_supported_reason(mode, retrieve_status),
    )


def _result_decision(
    mode: str,
    claims: list[str],
    unknown: list[str],
    citations: list[str],
    claim_results: list[dict[str, Any]],
    *,
    status: str,
    reason: str,
    action: str = "generate",
    unsupported_claims: list[str] | None = None,
) -> VerifyDecision:
    return VerifyDecision(
        mode=mode,
        status=status,
        reason=reason,
        action=action,
        claims=claims,
        unsupported_claims=unsupported_claims or [],
        unknown_claims=unknown,
        verified_citations=citations,
        claim_results=claim_results,
    )


def _unsupported_and_unknown(
    results: list[VerifiedClaim],
    evidence_items: list[dict[str, Any]],
    *,
    mode: str,
    prompt: str,
    domain: str,
) -> tuple[list[str], list[str]]:
    unsupported = [
        result.claim
        for result in results
        if result.status == "contradicted"
        or (
            result.status == "unknown"
            and unsupported_confidence(
                result.claim,
                evidence_items,
                prompt=prompt,
                domain=domain,
                mode=mode,
            )
            >= unsupported_threshold(mode=mode, domain=domain)
        )
    ]
    unknown = [
        result.claim
        for result in results
        if result.status in {"unknown", "conflicting"}
        and result.claim not in unsupported
    ]
    return unsupported, unknown


def _domain_supporting_identities(
    domain: str,
    claim: str,
    items: list[dict[str, Any]],
    *,
    prompt: str,
) -> tuple[str, ...]:
    return tuple(
        identity_of(item).key
        for item in items
        if domain_claim_supported(domain, claim, [item], prompt=prompt) is True
    )


def _can_verify_available_evidence(
    evidence_bundle: EvidenceBundle,
    claims: list[str],
) -> bool:
    return bool(claims and evidence_bundle.items)


def _supported_reason(mode: str, retrieve_status: str) -> str:
    if retrieve_status == "good":
        return (
            f"{mode.title()} verification requested; current verifier observed "
            "evidence."
        )
    return (
        f"{mode.title()} verification used available evidence despite "
        f"{retrieve_status} retrieval status."
    )


def _boolean_verification(
    prompt: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[list[str], list[VerifiedClaim]] | None:
    assessment = boolean_evidence_assessment(prompt, answer, evidence_items)
    if assessment is None:
        return None
    claim, status, supporting, contradicting = assessment
    result = VerifiedClaim(
        claim_id="claim:1",
        claim=claim,
        status=status,
        supporting_evidence_ids=supporting,
        contradicting_evidence_ids=contradicting,
    )
    return [claim], [result]


def _enforce_verification_slot_support(
    request: Any,
    decision: VerifyDecision,
) -> VerifyDecision:
    if decision.status != "supported":
        return decision
    supporting_ids = {
        evidence_id
        for result in decision.claim_results
        for evidence_id in result.get("supporting_evidence_ids") or []
    }
    unsupported_slots = [
        str(getattr(slot, "slot_id", "") or "")
        for slot in verification_slots(request)
        if str(getattr(slot, "role", "") or "") == "support"
        and not (
            supporting_ids
            & {
                str(value).strip()
                for value in getattr(slot, "evidence_ids", ()) or ()
                if str(value).strip()
            }
        )
    ]
    if not unsupported_slots:
        return decision
    return VerifyDecision(
        mode=decision.mode,
        status="unknown",
        reason=(
            "Verification-required slots did not support any verified claim: "
            + ", ".join(unsupported_slots)
        ),
        action="abstain",
        claims=decision.claims,
        unknown_claims=decision.claims,
        verified_citations=decision.verified_citations,
        claim_results=decision.claim_results,
    )
