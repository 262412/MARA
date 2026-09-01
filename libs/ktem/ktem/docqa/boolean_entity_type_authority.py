from __future__ import annotations

import re
from typing import Any

from .boolean_authority_derivation import (
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from .boolean_authority_schema import (
    ENTITY_TYPE_JOIN_RULE,
    BooleanAuthorityDerivation,
    BooleanEvidenceAuthority,
)
from .boolean_empirical_actions import empirical_action_present
from .boolean_evidence_scope import (
    _actor,
    _scope_rejection,
    _section_role,
    evidence_item_text,
)
from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_conditions import non_authoritative_proposition_span
from .boolean_proposition_context import proposition_spans
from .boolean_proposition_evidence import exact_span_asserts_boolean_relation
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation
from .boolean_scope_quantifiers import _closed_quantifier
from .evidence_identity import identity_of
from .query_phrase_extraction import source_page_locator

_ENTITY_TYPE_TOKENS = {
    "corpus",
    "dataset",
    "framework",
    "method",
    "model",
    "system",
    "toolkit",
}
_DECLARATION_RE = re.compile(
    r"\b(?:we\s+)?(?:call|design|develop|introduce|name|present)\w*\b",
    flags=re.IGNORECASE,
)
_ENTITY_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:/[A-Za-z0-9]+)*\b")


def same_source_typed_entity_derivations(
    question: str,
    items: list[dict[str, Any]],
) -> tuple[
    tuple[BooleanAuthorityDerivation, tuple[BooleanEvidenceAuthority, ...]], ...
]:
    """Return explicit declaration-and-empirical proofs for a named entity type."""

    if (
        primary_boolean_relation(question) != "evaluate"
        or not empirical_action_present(question)
        or _closed_quantifier(question) != "none"
    ):
        return ()
    relation_tokens = _relation_surface_tokens("evaluate")
    arguments = _question_argument_tokens(question, relation_tokens) - {""}
    categories = arguments & _ENTITY_TYPE_TOKENS
    if len(categories) != 1:
        return ()
    category = next(iter(categories))
    declarations: dict[
        str,
        dict[str, BooleanEvidenceAuthority],
    ] = {}
    for item in items:
        identity = identity_of(item)
        for alias, authority in _declaration_authorities(item, category):
            declarations.setdefault(identity.source_id, {}).setdefault(alias, authority)
    if not declarations:
        return ()

    proofs = []
    for item in items:
        identity = identity_of(item)
        source_declarations = declarations.get(identity.source_id, {})
        proofs.extend(
            _item_entity_type_proofs(
                question,
                item,
                source_declarations,
                category=category,
                arguments=arguments,
            )
        )
    return tuple(sorted(proofs, key=lambda value: value[0].derivation_id))


def _item_entity_type_proofs(
    question: str,
    item: dict[str, Any],
    declarations: dict[str, BooleanEvidenceAuthority],
    *,
    category: str,
    arguments: set[str],
) -> list[tuple[BooleanAuthorityDerivation, tuple[BooleanEvidenceAuthority, ...]]]:
    proofs = []
    for span in proposition_spans(question, evidence_item_text(item)):
        if not _authoritative_empirical_span(question, item, span):
            continue
        aliases = sorted(set(declarations) & _distinctive_entity_aliases(span))
        for alias in aliases:
            empirical = _empirical_alias_authority(question, item, span, alias=alias)
            declaration = declarations[alias]
            if empirical is None or empirical.evidence_ref == declaration.evidence_ref:
                continue
            proofs.append(
                _entity_type_proof(
                    declaration,
                    empirical,
                    alias=alias,
                    category=category,
                    arguments=arguments,
                )
            )
    return proofs


def _entity_type_proof(
    declaration: BooleanEvidenceAuthority,
    empirical: BooleanEvidenceAuthority,
    *,
    alias: str,
    category: str,
    arguments: set[str],
) -> tuple[BooleanAuthorityDerivation, tuple[BooleanEvidenceAuthority, ...]]:
    conclusion_object = " ".join(sorted(arguments))
    conclusion = {
        "actor": empirical.actor,
        "predicate": "evaluate",
        "relation": "evaluate",
        "object": conclusion_object,
        "arguments": [conclusion_object],
        "polarity": "yes",
        "qualifier": empirical.qualifier,
        "quantifier": "none",
        "scope": empirical.section_scope,
        "section_scope": empirical.section_scope,
    }
    identity_payload = boolean_derivation_identity_payload(
        rule_id=ENTITY_TYPE_JOIN_RULE,
        premise_refs=(declaration.evidence_ref, empirical.evidence_ref),
        conclusion=conclusion,
        required_argument_tokens=(category,),
        bindings={"entity_alias": alias, "entity_type": category},
    )
    derivation = BooleanAuthorityDerivation(
        derivation_id=boolean_derivation_id(identity_payload),
        rule_id=ENTITY_TYPE_JOIN_RULE,
        premise_refs=(declaration.evidence_ref, empirical.evidence_ref),
        premise_evidence_ids=(declaration.evidence_id, empirical.evidence_id),
        conclusion=conclusion,
        required_argument_tokens=(category,),
        covered_argument_tokens=(category,),
        premise_contributions=(
            _entity_type_contribution(declaration, "entity_declaration", category),
            _entity_type_contribution(empirical, "empirical_relation", category),
        ),
        bindings=(("entity_alias", alias), ("entity_type", category)),
    )
    return derivation, (declaration, empirical)


def _entity_type_contribution(
    authority: BooleanEvidenceAuthority,
    role: str,
    category: str,
) -> dict[str, Any]:
    return {
        "evidence_id": authority.evidence_id,
        "evidence_ref": authority.evidence_ref,
        "role": role,
        "argument_tokens": [category],
    }


def _declaration_authorities(
    item: dict[str, Any],
    category: str,
) -> tuple[tuple[str, BooleanEvidenceAuthority], ...]:
    text = evidence_item_text(item)
    identity = identity_of(item)
    canonical_start = _optional_int(item.get("canonical_start"))
    category_re = re.compile(
        rf"\b{re.escape(category)}(?:s|es)?\b",
        flags=re.IGNORECASE,
    )
    output: list[tuple[str, BooleanEvidenceAuthority]] = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text):
        raw = match.group(0)
        quote = raw.strip()
        declaration = _DECLARATION_RE.search(quote)
        type_match = category_re.search(quote)
        if (
            not quote
            or declaration is None
            or type_match is None
            or declaration.end() >= type_match.start()
        ):
            continue
        aliases = _distinctive_entity_aliases(
            quote[declaration.end() : type_match.start()]
        )
        if not aliases:
            continue
        start = match.start() + len(raw) - len(raw.lstrip())
        end = start + len(quote)
        ref_start = canonical_start + start if canonical_start is not None else start
        ref_end = canonical_start + end if canonical_start is not None else end
        evidence_ref = f"{identity.key}#quote:{ref_start}:{ref_end}"
        source_id, page_label = source_page_locator(item)
        section_scope = _section_role(item, quote)
        if section_scope == "unknown":
            section_scope = "document"
        authority = BooleanEvidenceAuthority(
            evidence_id=identity.key,
            evidence_ref=evidence_ref,
            span_id=evidence_ref,
            quote=quote,
            span_start=start,
            span_end=end,
            canonical_start=(ref_start if canonical_start is not None else None),
            canonical_end=(ref_end if canonical_start is not None else None),
            actor="current_paper",
            section_scope=section_scope,
            relation="type",
            object=category,
            quantifier="none",
            polarity="yes",
            reason="explicit_same_source_entity_type_declaration",
            qualifier="none",
            source_id=source_id,
            page_label=page_label,
        )
        output.extend((alias, authority) for alias in sorted(aliases))
    return tuple(output)


def _empirical_alias_authority(
    question: str,
    item: dict[str, Any],
    span: str,
    *,
    alias: str,
) -> BooleanEvidenceAuthority | None:
    text = evidence_item_text(item)
    if text.count(span) != 1:
        return None
    start = text.find(span)
    end = start + len(span)
    canonical_start = _optional_int(item.get("canonical_start"))
    ref_start = canonical_start + start if canonical_start is not None else start
    ref_end = canonical_start + end if canonical_start is not None else end
    identity = identity_of(item)
    evidence_ref = f"{identity.key}#quote:{ref_start}:{ref_end}"
    source_id, page_label = source_page_locator(item)
    section_role = _section_role(item, span)
    return BooleanEvidenceAuthority(
        evidence_id=identity.key,
        evidence_ref=evidence_ref,
        span_id=evidence_ref,
        quote=span,
        span_start=start,
        span_end=end,
        canonical_start=(ref_start if canonical_start is not None else None),
        canonical_end=(ref_end if canonical_start is not None else None),
        actor=_actor(span, section_role),
        section_scope=section_role,
        relation="evaluate",
        object=alias,
        quantifier="none",
        polarity="yes",
        reason="same_source_entity_empirical_premise",
        qualifier=proposition_qualifier(span, question=question),
        source_id=source_id,
        page_label=page_label,
    )


def _authoritative_empirical_span(
    question: str,
    item: dict[str, Any],
    span: str,
) -> bool:
    if (
        not empirical_action_present(span)
        or non_authoritative_proposition_span(question, span)
        or not exact_span_asserts_boolean_relation(question, span)
    ):
        return False
    section_role = _section_role(item, span)
    actor = _actor(span, section_role)
    return not _scope_rejection(
        question,
        actor=actor,
        section_role=section_role,
        structured_scope_available=True,
        quote=span,
    )


def _distinctive_entity_aliases(value: str) -> set[str]:
    aliases: set[str] = set()
    for match in _ENTITY_TOKEN_RE.finditer(str(value or "")):
        for token in match.group(0).split("/"):
            if _distinctive_entity_token(token):
                aliases.add(token.casefold())
    return aliases


def _distinctive_entity_token(value: str) -> bool:
    return bool(
        len(value) >= 4
        and (
            (
                any(character.islower() for character in value)
                and any(character.isupper() for character in value[1:])
            )
            or value.isupper()
        )
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
