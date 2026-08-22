from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from typing import Any, TypeAlias

from .boolean_authority_derivation import (
    boolean_derivation_contract_status,
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_EVIDENCE_SET_RULE,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
    BooleanAuthorityDerivation,
    BooleanClaimAuthority,
    BooleanEvidenceAuthority,
    supported_boolean_claim,
)
from .boolean_claim_verification import canonical_boolean_answer_polarity
from .boolean_evidence_scope import (
    _actor,
    _scope_rejection,
    _section_role,
    evidence_item_text,
)
from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_context import normalized_object_tokens
from .boolean_proposition_polarity import evidence_polarity
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation
from .boolean_scope_quantifiers import _closed_quantifier
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .query_phrase_extraction import source_page_locator

LOGGER = logging.getLogger(__name__)

_GENERIC_SUBJECT_TOKENS = {
    "are",
    "author",
    "can",
    "classifier",
    "collection",
    "current",
    "dataset",
    "did",
    "do",
    "does",
    "experiment",
    "feature",
    "framework",
    "had",
    "has",
    "have",
    "is",
    "language",
    "method",
    "model",
    "paper",
    "study",
    "system",
    "task",
    "their",
    "they",
    "this",
    "toolkit",
    "was",
    "were",
    "work",
}

PropositionVerifier: TypeAlias = Callable[
    [Any, str, str, EvidenceBundle],
    Mapping[str, Any] | None,
]
ValidatedPremises: TypeAlias = tuple[
    tuple[BooleanEvidenceAuthority, ...] | None,
    dict[str, tuple[str, ...]],
    str,
    str,
]


def semantic_evidence_set_claim_authority(
    request: Any,
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
    verifier: PropositionVerifier,
) -> BooleanClaimAuthority | None:
    """Validate a verifier-selected exact premise set as one typed proposition."""

    response = _call_verifier(verifier, request, prompt, answer, bundle)
    if response is None:
        _record_trace(bundle, "failed", "semantic_verifier_failed")
        return None
    header, header_reason = _validated_header(response)
    if header is None:
        _record_trace(bundle, "rejected", header_reason)
        return None
    verdict, attestation = header
    if verdict == "insufficient_evidence":
        _record_trace(bundle, "insufficient", "semantic_evidence_set_insufficient")
        return None
    premises, slot_support, scope_basis, premise_reason = _validated_premises(
        request,
        prompt,
        verdict,
        response.get("premises"),
        bundle.items,
    )
    if premises is None:
        _record_trace(bundle, "rejected", premise_reason)
        return None
    attestation = {
        **attestation,
        "premise_count": len(premises),
        "complete_proposition": True,
        "scope_basis": scope_basis,
        "required_slot_ids": sorted(
            {slot_id for values in slot_support.values() for slot_id in values}
        ),
    }
    derivation = _semantic_derivation(
        prompt,
        verdict,
        premises,
        attestation,
        slot_support=slot_support,
    )
    status = boolean_derivation_contract_status(
        derivation.as_dict(),
        [premise.as_dict() for premise in premises],
        question=prompt,
        canonical_polarity=verdict,
    )
    if status != "bound":
        _record_trace(bundle, "rejected", status)
        return None
    _record_trace(
        bundle,
        "verified",
        "semantic_evidence_set_bound",
        premise_count=len(premises),
        derivation_id=derivation.derivation_id,
    )
    return supported_boolean_claim(
        prompt,
        canonical_boolean_answer_polarity(answer),
        verdict,
        premises,
        reason="semantic_evidence_set_proposition",
        authority_derivations=(derivation,),
        selected_derivation_id=derivation.derivation_id,
    )


def _call_verifier(
    verifier: PropositionVerifier,
    request: Any,
    prompt: str,
    answer: str,
    bundle: EvidenceBundle,
) -> Mapping[str, Any] | None:
    try:
        response = verifier(request, prompt, answer, bundle)
    except Exception:
        LOGGER.exception("Semantic proposition verifier failed")
        return None
    return response if isinstance(response, Mapping) else None


def _validated_header(
    response: Mapping[str, Any],
) -> tuple[tuple[str, dict[str, Any]] | None, str]:
    if response.get("contract_id") != SEMANTIC_PROPOSITION_VERDICT_CONTRACT:
        return None, "semantic_verdict_contract_mismatch"
    verdict = str(response.get("verdict") or "")
    if verdict not in {"yes", "no", "insufficient_evidence"}:
        return None, "semantic_verdict_invalid"
    if response.get("support_mode") != "evidence_set":
        return None, "semantic_support_mode_invalid"
    if verdict in {"yes", "no"} and (
        response.get("jointly_complete") is not True
        or response.get("each_premise_required") is not True
    ):
        return None, "semantic_joint_entailment_incomplete"
    verifier = response.get("verifier")
    if not isinstance(verifier, Mapping):
        return None, "semantic_verifier_attestation_missing"
    model = str(verifier.get("model") or "").strip()
    if verifier.get("contract_id") != GROUNDED_SEMANTIC_VERIFIER_CONTRACT or not model:
        return None, "semantic_verifier_attestation_invalid"
    attestation = {
        "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
        "verdict_contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "model": model,
        "seed": verifier.get("seed"),
        "verdict": verdict,
        "jointly_complete": response.get("jointly_complete") is True,
        "each_premise_required": response.get("each_premise_required") is True,
    }
    return (verdict, attestation), ""


def _validated_premises(
    request: Any,
    question: str,
    verdict: str,
    raw_premises: Any,
    items: list[dict[str, Any]],
) -> ValidatedPremises:
    if not isinstance(raw_premises, list) or any(
        not isinstance(value, Mapping) for value in raw_premises
    ):
        return None, {}, "", "semantic_premise_schema_invalid"
    records = raw_premises
    if not 2 <= len(records) <= 4:
        return None, {}, "", "semantic_premise_count_invalid"
    required_slot_ids = _required_slot_ids(request)
    if not required_slot_ids:
        return None, {}, "", "semantic_required_slots_missing"
    lookup = _canonical_item_lookup(items)
    premises: list[BooleanEvidenceAuthority] = []
    slot_support: dict[str, tuple[str, ...]] = {}
    proposition_fragments: set[str] = set()
    for record in records:
        authority, reason = _validated_premise(
            question,
            verdict,
            record,
            lookup,
        )
        if authority is None:
            return None, {}, "", reason
        raw_supports = record.get("supports_slot_ids")
        if not isinstance(raw_supports, list):
            return None, {}, "", "semantic_premise_slot_binding_invalid"
        supports = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in raw_supports
                if isinstance(value, str) and value.strip()
            )
        )
        if not supports or any(value not in required_slot_ids for value in supports):
            return None, {}, "", "semantic_premise_slot_binding_invalid"
        fragment = str(record.get("proposition_fragment") or "").strip()
        normalized_fragment = " ".join(fragment.casefold().split())
        if (
            not fragment
            or len(fragment) > 320
            or normalized_fragment in proposition_fragments
        ):
            return None, {}, "", "semantic_premise_fragment_invalid"
        proposition_fragments.add(normalized_fragment)
        premises.append(authority)
        slot_support[authority.evidence_ref] = supports
    if len({value.evidence_ref for value in premises}) != len(premises):
        return None, {}, "", "semantic_premise_duplicate"
    if len({value.source_id for value in premises}) != 1:
        return None, {}, "", "semantic_premise_cross_source"
    if _premises_overlap(premises):
        return None, {}, "", "semantic_premise_overlap"
    scope_basis = _semantic_scope_basis(question, premises)
    if not scope_basis:
        return None, {}, "", "semantic_proposition_scope_incomplete"
    if (
        verdict == "no"
        and evidence_polarity(
            question,
            " ".join(value.quote for value in premises),
            desired_polarity="no",
        )
        != "no"
    ):
        return None, {}, "", "semantic_negative_authority_not_explicit"
    covered_slots = {value for values in slot_support.values() for value in values}
    if covered_slots != required_slot_ids:
        return None, {}, "", "semantic_required_slot_coverage_incomplete"
    return tuple(premises), slot_support, scope_basis, ""


def _canonical_item_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any] | None]:
    lookup: dict[str, dict[str, Any] | None] = {}
    for item in items:
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            continue
        lookup[evidence_id] = item if evidence_id not in lookup else None
    return lookup


def _validated_premise(
    question: str,
    verdict: str,
    record: Mapping[str, Any],
    lookup: dict[str, dict[str, Any] | None],
) -> tuple[BooleanEvidenceAuthority | None, str]:
    evidence_id = str(record.get("evidence_id") or "").strip()
    quote = str(record.get("quote") or "").strip()
    proposition_fragment = str(record.get("proposition_fragment") or "").strip()
    item = lookup.get(evidence_id)
    if item is None:
        return None, "semantic_premise_identity_unresolved"
    text = evidence_item_text(item)
    if not quote or len(quote) > 640 or text.count(quote) != 1:
        return None, "semantic_premise_quote_unbound"
    start = text.find(quote)
    end = start + len(quote)
    section_scope = _section_role(item, quote)
    actor = _actor(quote, section_scope)
    scope_rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_scope,
        structured_scope_available=section_scope != "unknown",
        quote=quote,
    )
    if section_scope == "future_work" or (
        scope_rejection
        and not (
            scope_rejection == "current_paper_scope_not_established"
            and actor == "unknown"
        )
    ):
        return None, "semantic_premise_scope_rejected"
    if actor == "unknown":
        actor = "local_source"
    if section_scope == "unknown":
        section_scope = "document"
    canonical_start = _optional_int(item.get("canonical_start"))
    ref_start = canonical_start + start if canonical_start is not None else start
    ref_end = canonical_start + end if canonical_start is not None else end
    source_id, page_label = source_page_locator(item)
    evidence_ref = f"{evidence_id}#quote:{ref_start}:{ref_end}"
    return (
        BooleanEvidenceAuthority(
            evidence_id=evidence_id,
            evidence_ref=evidence_ref,
            span_id=evidence_ref,
            quote=quote,
            span_start=start,
            span_end=end,
            canonical_start=(ref_start if canonical_start is not None else None),
            canonical_end=(ref_end if canonical_start is not None else None),
            actor=actor,
            section_scope=section_scope,
            relation="semantic_premise",
            object=proposition_fragment,
            quantifier="none",
            polarity=verdict,
            reason="semantic_evidence_set_premise",
            qualifier="none",
            source_id=source_id,
            page_label=page_label,
        ),
        "",
    )


def _semantic_derivation(
    question: str,
    verdict: str,
    premises: tuple[BooleanEvidenceAuthority, ...],
    attestation: dict[str, Any],
    *,
    slot_support: dict[str, tuple[str, ...]],
) -> BooleanAuthorityDerivation:
    relation = primary_boolean_relation(question) or "entails"
    required = tuple(
        sorted(
            token
            for token in _question_argument_tokens(
                question,
                _relation_surface_tokens(relation),
            )
            if token
        )
    )
    if not required:
        required = ("complete_proposition",)
    conclusion_object = (
        " ".join(required)
        if required != ("complete_proposition",)
        else question.strip()
    )
    actors = {value.actor for value in premises}
    scopes = {value.section_scope for value in premises}
    conclusion = {
        "actor": next(iter(actors)) if len(actors) == 1 else "current_source",
        "predicate": relation,
        "relation": relation,
        "object": conclusion_object,
        "arguments": [conclusion_object],
        "polarity": verdict,
        "qualifier": proposition_qualifier(question),
        "quantifier": _closed_quantifier(question),
        "scope": next(iter(scopes)) if len(scopes) == 1 else "document",
        "section_scope": next(iter(scopes)) if len(scopes) == 1 else "document",
    }
    contributions = tuple(
        {
            "evidence_id": premise.evidence_id,
            "evidence_ref": premise.evidence_ref,
            "role": f"semantic_premise:{index}",
            "order": index,
            "argument_tokens": [],
            "proposition_fragment": premise.object,
            "supports_slot_ids": list(slot_support[premise.evidence_ref]),
        }
        for index, premise in enumerate(premises, start=1)
    )
    identity = boolean_derivation_identity_payload(
        rule_id=SEMANTIC_EVIDENCE_SET_RULE,
        premise_refs=tuple(value.evidence_ref for value in premises),
        conclusion=conclusion,
        required_argument_tokens=required,
        support_mode="evidence_set",
        verifier_attestation=attestation,
        premise_contributions=contributions,
    )
    return BooleanAuthorityDerivation(
        derivation_id=boolean_derivation_id(identity),
        rule_id=SEMANTIC_EVIDENCE_SET_RULE,
        premise_refs=tuple(value.evidence_ref for value in premises),
        premise_evidence_ids=tuple(value.evidence_id for value in premises),
        conclusion=conclusion,
        required_argument_tokens=required,
        covered_argument_tokens=required,
        premise_contributions=contributions,
        support_mode="evidence_set",
        verifier_attestation=attestation,
    )


def _premises_overlap(premises: list[BooleanEvidenceAuthority]) -> bool:
    for index, left in enumerate(premises):
        for right in premises[index + 1 :]:
            if left.evidence_id != right.evidence_id:
                continue
            if max(left.span_start, right.span_start) < min(
                left.span_end, right.span_end
            ):
                return True
    return False


def _semantic_scope_basis(
    question: str,
    premises: list[BooleanEvidenceAuthority],
) -> str:
    actors = {value.actor for value in premises}
    if _explicit_current_paper_question(question):
        return "explicit_current_actor" if "current_paper" in actors else ""
    if "current_paper" in actors:
        return "explicit_current_actor"
    if actors & {"cited_work", "other_authors"}:
        return "explicit_prior_work_actor"
    return (
        "named_question_subject"
        if _named_question_subject_anchored(question, premises)
        else ""
    )


def _explicit_current_paper_question(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:the authors?|this (?:paper|article|study|work)|"
            r"current (?:paper|study|work)|they|their)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
    )


def _named_question_subject_anchored(
    question: str,
    premises: list[BooleanEvidenceAuthority],
) -> bool:
    relation = primary_boolean_relation(question)
    relation_tokens = _relation_surface_tokens(relation)
    if not relation_tokens:
        return False
    pattern = re.compile(
        r"\b(?:"
        + "|".join(
            re.escape(value) for value in sorted(relation_tokens, key=len, reverse=True)
        )
        + r")\b",
        flags=re.IGNORECASE,
    )
    match = pattern.search(str(question or ""))
    if match is None:
        return False
    subject_tokens = (
        normalized_object_tokens(
            str(question or "")[: match.start()],
            relation_tokens,
        )
        - _GENERIC_SUBJECT_TOKENS
    )
    subject_tokens = {value for value in subject_tokens if len(value) >= 3}
    evidence_tokens = normalized_object_tokens(
        " ".join(value.quote for value in premises),
        set(),
    )
    return bool(subject_tokens & evidence_tokens)


def _required_slot_ids(request: Any) -> set[str]:
    plan = getattr(request, "query_plan", None)
    return {
        str(getattr(slot, "slot_id", "") or "")
        for slot in getattr(plan, "evidence_slots", ()) or ()
        if bool(getattr(slot, "required_for_verification", False))
        and str(getattr(slot, "slot_id", "") or "")
    }


def _record_trace(
    bundle: EvidenceBundle,
    status: str,
    reason: str,
    **fields: Any,
) -> None:
    bundle.metadata["semantic_proposition_authority"] = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "status": status,
        "reason": reason,
        **fields,
    }


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
