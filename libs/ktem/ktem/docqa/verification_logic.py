from __future__ import annotations

from typing import Any

from .boolean_authoritative_conflict import conflict_sides_are_complete
from .boolean_verification_projection import (
    boolean_verification as _boolean_verification,
)
from .calculation_claim_verification import calculation_claim_result
from .claim_clauses import split_claim_clauses
from .claim_filtering import answer_claims
from .claim_support import (
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
from .layered_claim_support import layered_claim_supporting_ids
from .query_planning import request_planning_question
from .verification_layered_policy import (
    contradictory_extension_decision as _contradictory_extension_decision,
)
from .verification_layered_policy import (
    contradictory_extensions as _contradictory_extensions,
)
from .verification_schema import VerifiedClaim, VerifyDecision


def normalize_verification_mode(value: Any) -> str:
    mode = str(value or "off").strip().lower()
    return mode if mode in {"off", "light", "strict"} else "off"


def _calculation_verification_results(
    typed_calculation: Any,
    claims: list[str],
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
    domain: str,
) -> list[VerifiedClaim]:
    results: list[VerifiedClaim] = []
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


def _verification_results(
    claims: list[str],
    evidence_bundle: EvidenceBundle,
    answer: str,
    *,
    prompt: str,
    domain: str,
) -> tuple[list[str], list[VerifiedClaim]]:
    calculation_claims = split_claim_clauses(claims) if domain == "finance" else claims
    typed_calculation = calculation_claim_result(
        evidence_bundle, answer, calculation_claims, domain=domain, prompt=prompt
    )
    if typed_calculation is not None:
        return calculation_claims, _calculation_verification_results(
            typed_calculation,
            calculation_claims,
            evidence_bundle.items,
            prompt=prompt,
            domain=domain,
        )
    typed_domain = _domain_verification(
        claims,
        evidence_bundle.items,
        prompt=prompt,
        domain=domain,
    )
    if typed_domain is not None:
        return claims, typed_domain
    typed_boolean = _boolean_verification(prompt, answer, evidence_bundle.items)
    if typed_boolean is not None:
        return typed_boolean
    return claims, _verify_claims(claims, evidence_bundle.items, prompt, domain)


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
    if not supporting:
        supporting = list(
            layered_claim_supporting_ids(
                claim,
                evidence_items,
                prompt=prompt,
            )
        )
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
    if contradicting:
        return VerifiedClaim(
            claim_id=claim_id,
            claim=claim,
            status="contradicted",
            contradicting_evidence_ids=tuple(dict.fromkeys(contradicting)),
        )
    return VerifiedClaim(claim_id=claim_id, claim=claim, status="unknown")


def _domain_verification(
    claims: list[str],
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str,
    domain: str,
) -> list[VerifiedClaim] | None:
    support = [
        domain_claim_supported(
            domain,
            claim,
            evidence_items,
            prompt=prompt,
        )
        for claim in claims
    ]
    if not support or any(value is None for value in support):
        return None
    return [
        VerifiedClaim(
            claim_id=f"claim:{index}",
            claim=claim,
            status="supported" if supported else "contradicted",
            supporting_evidence_ids=(
                _domain_supporting_identities(
                    domain,
                    claim,
                    evidence_items,
                    prompt=prompt,
                )
                if supported
                else ()
            ),
        )
        for index, (claim, supported) in enumerate(zip(claims, support), start=1)
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
    decision_metadata = _claim_decision_metadata(results)
    unsupported, unknown = _unsupported_and_unknown(
        results,
        evidence_items,
        mode=mode,
        prompt=prompt,
        domain=domain,
    )
    citations = _supported_citations(results)
    serialized = [result.as_dict() for result in results]
    if _verified_authoritative_conflict(results):
        return _authoritative_conflict_decision(
            mode,
            claims,
            serialized,
            decision_metadata,
        )
    contradictory_extensions = _contradictory_extensions(results)
    if contradictory_extensions and results and results[0].status == "supported":
        return _contradictory_extension_decision(
            mode,
            claims,
            serialized,
            contradictory_extensions,
            decision_metadata,
        )
    return _claim_result_outcome(
        mode,
        retrieve_status,
        claims,
        results,
        unsupported,
        unknown,
        citations,
        serialized,
        decision_metadata,
    )


def _claim_result_outcome(
    mode: str,
    retrieve_status: str,
    claims: list[str],
    results: list[VerifiedClaim],
    unsupported: list[str],
    unknown: list[str],
    citations: list[str],
    serialized: list[dict[str, Any]],
    decision_metadata: dict[str, Any],
) -> VerifyDecision:
    if unsupported:
        return _unsupported_claim_decision(
            mode,
            claims,
            unknown,
            citations,
            serialized,
            unsupported,
            decision_metadata,
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
                decision_metadata=decision_metadata,
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
            action="abstain",
            decision_metadata=decision_metadata,
        )
    return _result_decision(
        mode,
        claims,
        unknown,
        citations,
        serialized,
        status="supported",
        reason=_supported_reason(mode, retrieve_status),
        decision_metadata=decision_metadata,
    )


def _authoritative_conflict_decision(
    mode: str,
    claims: list[str],
    serialized: list[dict[str, Any]],
    decision_metadata: dict[str, Any],
) -> VerifyDecision:
    return _result_decision(
        mode,
        claims,
        [],
        [],
        serialized,
        status="verified_conflict",
        reason="authoritative_conflict_abstention",
        action="abstain",
        decision_metadata=decision_metadata,
    )


def _unsupported_claim_decision(
    mode: str,
    claims: list[str],
    unknown: list[str],
    citations: list[str],
    serialized: list[dict[str, Any]],
    unsupported: list[str],
    decision_metadata: dict[str, Any],
) -> VerifyDecision:
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
        decision_metadata=decision_metadata,
    )


def _supported_citations(results: list[VerifiedClaim]) -> list[str]:
    return list(
        dict.fromkeys(
            evidence_id
            for result in results
            if result.status == "supported"
            for evidence_id in result.supporting_evidence_ids
        )
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
    decision_metadata: dict[str, Any] | None = None,
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
        **(decision_metadata or {}),
    )


def _claim_decision_metadata(results: list[VerifiedClaim]) -> dict[str, Any]:
    typed = next(
        (
            result
            for result in results
            if result.canonical_answer_polarity or result.authoritative_conflict
        ),
        None,
    )
    if typed is None:
        return {}
    return {
        "input_answer_polarity": typed.input_answer_polarity,
        "canonical_answer_polarity": typed.canonical_answer_polarity,
        "semantic_correction_applied": typed.semantic_correction_applied,
        "boolean_authority_status": typed.authority_status,
        "authoritative_evidence_id": typed.authoritative_evidence_id,
        "authoritative_evidence_ref": typed.authoritative_evidence_ref,
        "authoritative_span_id": typed.authoritative_span_id,
        "authoritative_quote": typed.authoritative_quote,
        "authoritative_span_start": typed.authoritative_span_start,
        "authoritative_span_end": typed.authoritative_span_end,
        "authoritative_canonical_start": typed.authoritative_canonical_start,
        "authoritative_canonical_end": typed.authoritative_canonical_end,
        "actor": typed.actor,
        "section_scope": typed.section_scope,
        "relation": typed.relation,
        "object": typed.object,
        "predicate_arguments": typed.predicate_arguments,
        "qualifier": typed.qualifier,
        "quantifier": typed.quantifier,
        "authority_derivations": typed.authority_derivations,
        "selected_derivation_id": typed.selected_derivation_id,
        "authoritative_conflict": typed.authoritative_conflict,
    }


def _verified_authoritative_conflict(results: list[VerifiedClaim]) -> bool:
    conflicts = [
        result
        for result in results
        if result.status == "conflicting" and result.authoritative_conflict
    ]
    return bool(
        len(conflicts) == 1
        and len(results) == 1
        and conflict_sides_are_complete(conflicts[0].authoritative_conflict)
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


__all__ = [
    "VerifiedClaim",
    "VerifyDecision",
    "normalize_verification_mode",
    "verify_claim",
    "_boolean_verification",
    "_calculation_verification_results",
    "_can_verify_available_evidence",
    "_decision_for_claim_results",
    "_domain_verification",
    "_verification_results",
    "_verification_context",
    "_verify_claims",
]
