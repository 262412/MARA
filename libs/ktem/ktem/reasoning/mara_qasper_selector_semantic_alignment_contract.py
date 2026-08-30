from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from ktem.docqa.question_proposition import (
    QuestionProposition,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
    canonical_semantic_token,
)

ALIGNMENT_CONTRACT = "qasper_selector_semantic_alignment.v1"
OBJECT_SYNONYM_RULES: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "one": (
        (
            "indefinite_singular",
            re.compile(
                r"\b(?:a|an)\s+(?:[A-Z][A-Z0-9-]{1,}|[A-Za-z]+)\b|"
                r"\b(?:one|single)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    "pair": (
        (
            "paired_cardinality",
            re.compile(
                r"\b(?:two|both)\s+(?:[A-Za-z-]+\s+){0,2}[A-Za-z-]+\b",
                re.IGNORECASE,
            ),
        ),
        (
            "paired_relation",
            re.compile(r"\b(?:pair(?:ed)?|coupl(?:e|ed|ing)|between)\b", re.I),
        ),
    ),
    "part": (
        (
            "part_surface_synonym",
            re.compile(
                r"\b(?:context|feature|object|region|signal|tag)s?\b",
                re.IGNORECASE,
            ),
        ),
    ),
    "word": (
        (
            "word_surface_synonym",
            re.compile(
                r"\b(?:caption|text|textual|token)s?\b",
                re.IGNORECASE,
            ),
        ),
    ),
    "associate": (
        (
            "semantic_relation_synonym",
            re.compile(
                r"\b(?:align|aligned|alignment|affect|affects|affected|"
                r"attend|attends|attention|connect|connected|correspond|"
                r"corresponding|focus|focuses|link|linked|similarities|"
                r"similarity)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    "relat": (
        (
            "semantic_relation_synonym",
            re.compile(
                r"\b(?:align|aligned|alignment|affect|affects|affected|"
                r"attend|attends|attention|connect|connected|correspond|"
                r"corresponding|focus|focuses|link|linked|similarities|"
                r"similarity)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    "learn": (
        (
            "learning_process_synonym",
            re.compile(
                r"\b(?:capture|captured|learn|learned|learnt|train|trained|"
                r"training)\b",
                re.IGNORECASE,
            ),
        ),
    ),
}
CURRENT_PAPER_ANALYSIS_HEADING_RE = re.compile(
    r"^\s*(?:error|qualitative|quantitative|case|model)?\s*"
    r"(?:analysis|inspection|visualization|visualisation)\s*:",
    re.IGNORECASE,
)

_ALIGNMENT_RELATIONS = {
    "proposition_support",
    "explicit_contradiction",
    "undetermined",
}
_ALIGNMENT_STATES = {
    "affirmative_assertion",
    "explicit_contradiction",
    "unbound",
}
_LOCAL_ALIGNMENT_RULE_IDS = {
    rule_id for rules in OBJECT_SYNONYM_RULES.values() for rule_id, _ in rules
} | {
    "exact_semantic_token",
    "current_paper_analysis_heading",
}


def verified_selector_semantic_alignment(
    question: str,
    selector: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw = selector.get("semantic_alignment")
    if not isinstance(raw, Mapping):
        return None
    payload = dict(raw)
    proposition = build_question_proposition(question)
    if not _alignment_header_valid(payload, selector, proposition):
        return None
    slot_refs = payload.get("slot_refs")
    if not _alignment_slots_valid(slot_refs, selector):
        return None
    token_sets = _alignment_token_sets(payload, proposition)
    if token_sets is None:
        return None
    _required, covered = token_sets
    if not _alignment_relation_valid(payload, selector, slot_refs):
        return None
    if not _alignment_rules_valid(payload, selector, covered_tokens=covered):
        return None
    without_digest = {
        key: value for key, value in payload.items() if key != "alignment_digest"
    }
    if payload.get("alignment_digest") != canonical_payload_digest(without_digest):
        return None
    return payload


def _alignment_header_valid(
    payload: Mapping[str, Any],
    selector: Mapping[str, Any],
    proposition: QuestionProposition,
) -> bool:
    if (
        payload.get("contract_id") != ALIGNMENT_CONTRACT
        or payload.get("status") != "verified"
    ):
        return False
    expected = {
        "proposition_id": proposition.proposition_id,
        "evidence_id": str(selector.get("evidence_id") or ""),
        "selector_id": str(selector.get("selector_id") or ""),
        "span_start": selector.get("span_start"),
        "span_end": selector.get("span_end"),
        "text_digest": canonical_payload_digest(str(selector.get("text") or "")),
        "event_id": str(selector.get("event_id") or ""),
    }
    return not any(payload.get(key) != value for key, value in expected.items())


def _alignment_slots_valid(value: Any, selector: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    slots = {
        str(slot) for slot in selector.get("slot_hints") or [] if str(slot).strip()
    }
    selector_id = str(selector.get("selector_id") or "")
    return set(value) == slots and all(
        str(selector_ref) == selector_id for selector_ref in value.values()
    )


def _alignment_token_sets(
    payload: Mapping[str, Any],
    proposition: QuestionProposition,
) -> tuple[set[str], set[str]] | None:
    required = payload.get("required_object_tokens")
    covered = payload.get("covered_object_tokens")
    if not isinstance(required, (list, tuple, set)) or not isinstance(
        covered, (list, tuple, set)
    ):
        return None
    required_set = {str(token) for token in required}
    covered_set = {str(token) for token in covered}
    expected = canonical_proposition_object_token_set(proposition)
    if required_set != expected or not covered_set <= expected:
        return None
    return required_set, covered_set


def _alignment_relation_valid(
    payload: Mapping[str, Any],
    selector: Mapping[str, Any],
    slot_refs: Any,
) -> bool:
    predicate_kind = str(payload.get("predicate_match_kind") or "")
    local_state = str(selector.get("local_relation_state") or "")
    polarity = str(payload.get("polarity_relation") or "")
    expected_polarity = {
        "affirmative_assertion": "proposition_support",
        "explicit_contradiction": "explicit_contradiction",
        "unbound": "undetermined",
    }.get(local_state)
    return bool(
        str(payload.get("predicate_concept") or "")
        and predicate_kind in {"exact", "alias", "paraphrase", "missing"}
        and predicate_kind == str(selector.get("predicate_match_kind") or "")
        and polarity in _ALIGNMENT_RELATIONS
        and local_state in _ALIGNMENT_STATES
        and str(payload.get("local_relation_state") or "") == local_state
        and polarity == expected_polarity
        and (predicate_kind == "missing") == ("predicate" not in set(slot_refs or {}))
    )


def _alignment_rules_valid(
    payload: Mapping[str, Any],
    selector: Mapping[str, Any],
    *,
    covered_tokens: set[str],
) -> bool:
    rule_ids = payload.get("semantic_rule_ids")
    matches = payload.get("semantic_matches")
    if not isinstance(rule_ids, (list, tuple, set)) or not isinstance(matches, Mapping):
        return False
    observed_rule_ids = {str(value) for value in rule_ids}
    return bool(
        observed_rule_ids <= _LOCAL_ALIGNMENT_RULE_IDS
        and _semantic_matches_valid(
            matches,
            selector,
            covered_tokens=covered_tokens,
        )
        and _semantic_rule_ids_match(
            payload,
            selector,
            matches,
            observed_rule_ids=observed_rule_ids,
        )
    )


def _semantic_rule_ids_match(
    payload: Mapping[str, Any],
    selector: Mapping[str, Any],
    matches: Mapping[str, Any],
    *,
    observed_rule_ids: set[str],
) -> bool:
    match_rule_ids = {
        str(raw_match.get("rule_id") or "")
        for raw_matches in matches.values()
        if isinstance(raw_matches, (list, tuple))
        for raw_match in raw_matches
        if isinstance(raw_match, Mapping)
    }
    allowed_extras: set[str] = set()
    if (
        "current_paper_analysis_heading" in observed_rule_ids
        and "actor" in set(dict(payload.get("slot_refs") or {}))
        and CURRENT_PAPER_ANALYSIS_HEADING_RE.search(str(selector.get("text") or ""))
    ):
        allowed_extras.add("current_paper_analysis_heading")
    return observed_rule_ids == match_rule_ids | allowed_extras


def _semantic_matches_valid(
    value: Any,
    selector: Mapping[str, Any],
    *,
    covered_tokens: set[str],
) -> bool:
    if not isinstance(value, Mapping) or set(value) != covered_tokens:
        return False
    parent_start = selector.get("span_start")
    parent_end = selector.get("span_end")
    parent_text = str(selector.get("text") or "")
    if not isinstance(parent_start, int) or not isinstance(parent_end, int):
        return False
    return all(
        _semantic_match_valid(
            str(token),
            raw_match,
            parent_start=parent_start,
            parent_end=parent_end,
            parent_text=parent_text,
        )
        for token, raw_matches in value.items()
        if isinstance(raw_matches, (list, tuple)) and raw_matches
        for raw_match in raw_matches
    ) and all(
        isinstance(raw_matches, (list, tuple)) and bool(raw_matches)
        for raw_matches in value.values()
    )


def _semantic_match_valid(
    token: str,
    value: Any,
    *,
    parent_start: int,
    parent_end: int,
    parent_text: str,
) -> bool:
    if not isinstance(value, Mapping):
        return False
    start = value.get("span_start")
    end = value.get("span_end")
    text = str(value.get("text") or "")
    kind = str(value.get("match_kind") or "")
    rule_id = str(value.get("rule_id") or "")
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or not parent_start <= start < end <= parent_end
        or parent_text[start - parent_start : end - parent_start] != text
        or kind not in {"exact", "synonym"}
        or rule_id not in _LOCAL_ALIGNMENT_RULE_IDS
    ):
        return False
    if kind == "exact":
        return canonical_semantic_token(text) == token
    return any(
        candidate_rule == rule_id and pattern.fullmatch(text)
        for candidate_rule, pattern in OBJECT_SYNONYM_RULES.get(token, ())
    )
