from __future__ import annotations

from collections import defaultdict
from typing import Any, TypeAlias

from .boolean_authority_derivation import (
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from .boolean_authority_schema import (
    ARGUMENT_CONJUNCTION_RULE,
    BooleanAuthorityDerivation,
    BooleanEvidenceAuthority,
)
from .boolean_conjunction import boolean_conjunction_spec
from .boolean_empirical_authority import direct_experiment_relation
from .boolean_evidence_scope import evidence_item_text
from .boolean_proposition_compatibility import boolean_argument_token_coverage
from .boolean_proposition_conditions import non_authoritative_proposition_span
from .boolean_proposition_evidence import (
    classify_boolean_evidence_candidates,
    exact_span_asserts_boolean_relation,
)
from .evidence_identity import identity_of
from .query_phrase_extraction import source_page_locator

CompositeBooleanProof: TypeAlias = tuple[
    BooleanAuthorityDerivation,
    tuple[BooleanEvidenceAuthority, ...],
]


def same_source_argument_conjunctions(
    question: str,
    items: list[dict[str, Any]],
) -> tuple[CompositeBooleanProof, ...]:
    """Compose complementary exact spans into one minimal positive proposition proof."""

    spec = boolean_conjunction_spec(question)
    if spec is None:
        return ()
    required = tuple(str(value) for value in spec["required_argument_tokens"])
    candidates = _argument_premises(question, items, required=set(required))
    by_source: dict[
        str, list[tuple[BooleanEvidenceAuthority, frozenset[str]]]
    ] = defaultdict(list)
    for authority, coverage in candidates:
        by_source[authority.source_id].append((authority, coverage))

    proofs: list[CompositeBooleanProof] = []
    for source_id in sorted(by_source):
        selected = _minimum_cover(
            by_source[source_id],
            required=frozenset(required),
            max_premises=int(spec["max_premises"]),
        )
        if selected is None:
            continue
        authorities = tuple(value[0] for value in selected)
        coverages = tuple(value[1] for value in selected)
        qualifiers = {value.qualifier for value in authorities}
        if len(qualifiers) != 1:
            continue
        scopes = {value.section_scope for value in authorities}
        conclusion_scope = next(iter(scopes)) if len(scopes) == 1 else "document"
        conclusion_object = " ".join(required)
        conclusion = {
            "actor": "current_paper",
            "predicate": authorities[0].relation,
            "relation": authorities[0].relation,
            "object": conclusion_object,
            "arguments": [conclusion_object],
            "polarity": "yes",
            "qualifier": next(iter(qualifiers)),
            "quantifier": str(spec["quantifier"]),
            "scope": conclusion_scope,
            "section_scope": conclusion_scope,
        }
        contributions = tuple(
            {
                "evidence_id": authority.evidence_id,
                "evidence_ref": authority.evidence_ref,
                "role": "argument_coverage",
                "argument_tokens": sorted(coverage),
            }
            for authority, coverage in selected
        )
        identity_payload = boolean_derivation_identity_payload(
            rule_id=ARGUMENT_CONJUNCTION_RULE,
            premise_refs=tuple(value.evidence_ref for value in authorities),
            conclusion=conclusion,
            required_argument_tokens=required,
        )
        derivation = BooleanAuthorityDerivation(
            derivation_id=boolean_derivation_id(identity_payload),
            rule_id=ARGUMENT_CONJUNCTION_RULE,
            premise_refs=tuple(value.evidence_ref for value in authorities),
            premise_evidence_ids=tuple(value.evidence_id for value in authorities),
            conclusion=conclusion,
            required_argument_tokens=required,
            covered_argument_tokens=tuple(sorted(set().union(*coverages))),
            premise_contributions=contributions,
        )
        proofs.append((derivation, authorities))
    return tuple(sorted(proofs, key=lambda value: value[0].derivation_id))


def _argument_premises(
    question: str,
    items: list[dict[str, Any]],
    *,
    required: set[str],
) -> list[tuple[BooleanEvidenceAuthority, frozenset[str]]]:
    output: dict[str, tuple[BooleanEvidenceAuthority, frozenset[str]]] = {}
    for item in items:
        for assessment in classify_boolean_evidence_candidates(question, "yes", item):
            span = assessment.span_text
            if not _premise_is_assertive(question, assessment, item, span):
                continue
            _required, covered = boolean_argument_token_coverage(question, span)
            coverage = frozenset(covered) & required
            if not coverage or coverage == required:
                continue
            authority = _premise_authority(item, assessment, coverage)
            if authority is None:
                continue
            output[authority.evidence_ref] = (authority, coverage)
    return sorted(
        output.values(),
        key=lambda value: (
            -len(value[1]),
            len(value[0].quote),
            value[0].evidence_ref,
        ),
    )


def _premise_is_assertive(
    question: str,
    assessment: Any,
    item: dict[str, Any],
    span: str,
) -> bool:
    proposition = assessment.proposition
    return bool(
        proposition.polarity == "yes"
        and proposition.actor == "current_paper"
        and proposition.section_scope not in {"future_work", "related_work"}
        and assessment.relation_score == 1.0
        and assessment.actor_score > 0
        and assessment.scope_score > 0
        and exact_span_asserts_boolean_relation(question, span)
        and not non_authoritative_proposition_span(question, span)
        and direct_experiment_relation(question, span, evidence_item_text(item))
    )


def _premise_authority(
    item: dict[str, Any],
    assessment: Any,
    coverage: frozenset[str],
) -> BooleanEvidenceAuthority | None:
    text = evidence_item_text(item)
    quote = str(assessment.span_text or "").strip()
    if not quote or text.count(quote) != 1:
        return None
    start = text.find(quote)
    end = start + len(quote)
    canonical_start = _optional_int(item.get("canonical_start"))
    canonical_end = canonical_start + end if canonical_start is not None else None
    ref_start = canonical_start + start if canonical_start is not None else start
    ref_end = canonical_end if canonical_end is not None else end
    identity = identity_of(item)
    evidence_ref = f"{identity.key}#quote:{ref_start}:{ref_end}"
    source_id, page_label = source_page_locator(item)
    section_scope = assessment.proposition.section_scope
    if section_scope == "unknown":
        section_scope = "document"
    return BooleanEvidenceAuthority(
        evidence_id=identity.key,
        evidence_ref=evidence_ref,
        span_id=evidence_ref,
        quote=quote,
        span_start=start,
        span_end=end,
        canonical_start=(ref_start if canonical_start is not None else None),
        canonical_end=canonical_end,
        actor="current_paper",
        section_scope=section_scope,
        relation=assessment.proposition.action,
        object=" ".join(sorted(coverage)),
        quantifier="none",
        polarity="yes",
        reason="composite_boolean_argument_premise",
        qualifier=assessment.proposition.qualifier,
        source_id=source_id,
        page_label=page_label,
    )


def _minimum_cover(
    candidates: list[tuple[BooleanEvidenceAuthority, frozenset[str]]],
    *,
    required: frozenset[str],
    max_premises: int,
) -> tuple[tuple[BooleanEvidenceAuthority, frozenset[str]], ...] | None:
    states: dict[
        frozenset[str],
        tuple[tuple[BooleanEvidenceAuthority, frozenset[str]], ...],
    ] = {frozenset(): ()}
    for candidate in candidates:
        for covered, partial_proof in list(states.items()):
            if len(partial_proof) >= max_premises or candidate[1] <= covered:
                continue
            if any(
                _premises_overlap(candidate[0], value[0]) for value in partial_proof
            ):
                continue
            updated = covered | candidate[1]
            proposed = (*partial_proof, candidate)
            current = states.get(updated)
            if current is None or _proof_rank(proposed) < _proof_rank(current):
                states[updated] = proposed
    selected = states.get(required)
    if selected is None or len(selected) < 2:
        return None
    if any(
        set().union(
            *(value[1] for offset, value in enumerate(selected) if offset != index)
        )
        == set(required)
        for index in range(len(selected))
    ):
        return None
    return selected


def _proof_rank(
    proof: tuple[tuple[BooleanEvidenceAuthority, frozenset[str]], ...],
) -> tuple[int, int, tuple[str, ...]]:
    return (
        len(proof),
        sum(len(value[0].quote) for value in proof),
        tuple(value[0].evidence_ref for value in proof),
    )


def _premises_overlap(
    left: BooleanEvidenceAuthority,
    right: BooleanEvidenceAuthority,
) -> bool:
    return bool(
        left.evidence_id == right.evidence_id
        and max(left.span_start, right.span_start) < min(left.span_end, right.span_end)
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
