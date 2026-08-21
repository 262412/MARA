from __future__ import annotations

import re
from typing import Any

from .boolean_authority_schema import BooleanEvidenceAuthority
from .boolean_empirical_actions import empirical_action_present
from .boolean_evidence_scope import (
    _actor,
    _scope_rejection,
    _section_role,
    evidence_item_text,
)
from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_conditions import non_authoritative_proposition_span
from .boolean_proposition_context import exact_proposition_context, proposition_spans
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


def same_source_typed_entity_authorities(
    question: str,
    items: list[dict[str, Any]],
) -> tuple[BooleanEvidenceAuthority, ...]:
    """Bind an empirical named entity to its explicit same-source type."""

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
    declarations: dict[str, set[str]] = {}
    for item in items:
        aliases = _declared_entity_aliases(evidence_item_text(item), category)
        if aliases:
            declarations.setdefault(identity_of(item).source_id, set()).update(aliases)
    if not declarations:
        return ()

    authorities: list[BooleanEvidenceAuthority] = []
    for item in items:
        identity = identity_of(item)
        declared_aliases = declarations.get(identity.source_id, set())
        if not declared_aliases:
            continue
        text = evidence_item_text(item)
        for span in proposition_spans(question, text):
            if not _authoritative_empirical_span(question, item, span):
                continue
            if not (declared_aliases & _distinctive_entity_aliases(span)):
                continue
            window = exact_proposition_context(
                text,
                span,
                canonical_start=_optional_int(item.get("canonical_start")),
            )
            if window is None:
                continue
            section_role = _section_role(item, span)
            actor = _actor(span, section_role)
            span_start = (
                window.canonical_start
                if window.canonical_start is not None
                else window.start
            )
            span_end = (
                window.canonical_end if window.canonical_end is not None else window.end
            )
            span_id = f"{identity.key}#quote:{span_start}:{span_end}"
            source_id, page_label = source_page_locator(item)
            authorities.append(
                BooleanEvidenceAuthority(
                    evidence_id=identity.key,
                    evidence_ref=span_id,
                    span_id=span_id,
                    quote=window.text,
                    span_start=window.start,
                    span_end=window.end,
                    canonical_start=window.canonical_start,
                    canonical_end=window.canonical_end,
                    actor=actor,
                    section_scope=section_role,
                    relation="evaluate",
                    object=" ".join(sorted(arguments)),
                    quantifier="none",
                    polarity="yes",
                    reason="same_source_entity_type_empirical_proposition",
                    qualifier=proposition_qualifier(span, question=question),
                    source_id=source_id,
                    page_label=page_label,
                )
            )
    return tuple(authorities)


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


def _declared_entity_aliases(value: str, category: str) -> set[str]:
    aliases: set[str] = set()
    category_re = re.compile(
        rf"\b{re.escape(category)}(?:s|es)?\b",
        flags=re.IGNORECASE,
    )
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", str(value or "")):
        sentence = match.group(0).strip()
        declaration = _DECLARATION_RE.search(sentence)
        type_match = category_re.search(sentence)
        if (
            declaration is None
            or type_match is None
            or declaration.end() >= type_match.start()
        ):
            continue
        aliases.update(
            _distinctive_entity_aliases(
                sentence[declaration.end() : type_match.start()]
            )
        )
    return aliases


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
