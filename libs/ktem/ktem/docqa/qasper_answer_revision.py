from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .boolean_proposition_polarity import target_relation_is_negated
from .evidence_identity import identity_of
from .query_classification import normalized_answer_type
from .query_phrase_extraction import source_page_locator
from .query_planning import ensure_request_query_plan, request_planning_question

ANSWER_REVISION_CONTRACT = "qasper_answer_revision.v1"

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)?", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
_CURRENT_PAPER_TERMS = re.compile(
    r"\b(?:we|our|ours|this\s+(?:paper|study|work|approach)|the\s+authors?)\b",
    re.IGNORECASE,
)
_RELATED_WORK_TERMS = re.compile(
    r"\b(?:related\s+work|prior\s+work|previous\s+work|background|literature)\b",
    re.IGNORECASE,
)
_QUALIFIER_RE = re.compile(
    r"\b(?:at\s+least|at\s+most|more\s+than|less\s+than|only|"
    r"approximately|about)\b",
    re.IGNORECASE,
)

_RELATION_ALIASES = {
    "leverage": ("leverage", "leverages", "leveraged", "leveraging"),
    "use": ("use", "uses", "used", "using"),
    "provide": ("provide", "provides", "provided", "providing"),
    "contain": ("contain", "contains", "contained", "containing"),
    "include": ("include", "includes", "included", "including"),
    "report": ("report", "reports", "reported", "reporting"),
    "describe": ("describe", "describes", "described", "describing"),
    "identify": ("identify", "identifies", "identified", "identifying"),
}


@dataclass(frozen=True, slots=True)
class AnswerRevisionProposal:
    revised_answer: str
    canonical_evidence_id: str
    evidence_ref: str
    span_id: str
    quote: str
    span_start: int
    span_end: int
    canonical_start: int | None
    canonical_end: int | None
    actor: str
    relation: str
    object: str
    qualifier: str
    scope: str
    revision_reason: str
    ambiguity_status: str
    conflict_status: str
    source_id: str
    page_label: str

    def as_dict(self) -> dict[str, Any]:
        return {"contract_id": ANSWER_REVISION_CONTRACT, **asdict(self)}


@dataclass(frozen=True, slots=True)
class AnswerRevisionAssessment:
    eligible: bool
    reason: str
    ambiguity_status: str
    conflict_status: str
    candidate_evidence_ids: tuple[str, ...] = ()
    proposal: AnswerRevisionProposal | None = None


def propose_qasper_answer_revision(
    request: Any,
    verify_decision: Any,
    evidence_items: list[dict[str, Any]],
) -> AnswerRevisionProposal | None:
    return assess_qasper_answer_revision(
        request,
        verify_decision,
        evidence_items,
    ).proposal


def assess_qasper_answer_revision(
    request: Any,
    verify_decision: Any,
    evidence_items: list[dict[str, Any]],
) -> AnswerRevisionAssessment:
    if not _eligible(request, verify_decision):
        return AnswerRevisionAssessment(False, "not_eligible", "not_attempted", "none")
    question = request_planning_question(request)
    relation = _question_relation(question)
    if not relation:
        return AnswerRevisionAssessment(
            True,
            "question_relation_unresolved",
            "no_unique_projection",
            "none",
        )
    candidates = [
        candidate
        for item in evidence_items
        for candidate in _item_candidates(item, question=question, relation=relation)
    ]
    candidate_ids = tuple(
        sorted({candidate.canonical_evidence_id for candidate in candidates})
    )
    if not candidates:
        return AnswerRevisionAssessment(
            True,
            "direct_answer_relation_missing",
            "no_unique_projection",
            "none",
        )
    if len({_normalized(candidate.object) for candidate in candidates}) != 1:
        return AnswerRevisionAssessment(
            True,
            "direct_answer_relation_ambiguous",
            "multiple_direct_objects",
            "potential_conflict",
            candidate_ids,
        )
    selected = _unique_direct_authority(candidates)
    return AnswerRevisionAssessment(
        True,
        "unique_direct_answer_relation",
        "unique",
        "none",
        candidate_ids,
        selected,
    )


def proposal_matches_verified_authority(
    proposal: AnswerRevisionProposal,
    verify_decision: Any,
) -> bool:
    authority = getattr(verify_decision, "typed_authority", {})
    authority = authority if isinstance(authority, dict) else {}
    atoms = [
        atom
        for atom in authority.get("authority_atoms") or []
        if isinstance(atom, dict)
    ]
    if len(atoms) != 1:
        return False
    atom = atoms[0]
    return bool(
        getattr(verify_decision, "status", "") == "supported"
        and getattr(verify_decision, "action", "") == "generate"
        and authority.get("state") == "verified_support"
        and authority.get("required_slot_ids") == ["support:answer_relation"]
        and authority.get("verified_slot_ids") == ["support:answer_relation"]
        and atom.get("evidence_id") == proposal.canonical_evidence_id
        and atom.get("quote") == proposal.quote
        and _ref_is_exact_quote_span(atom.get("evidence_ref"), atom, proposal)
        and _ref_is_exact_quote_span(atom.get("span_id"), atom, proposal)
        and atom.get("actor") == proposal.actor
        and _relations_equivalent(atom.get("relation"), proposal.relation)
        and atom.get("object") == proposal.object
        and atom.get("qualifier") == proposal.qualifier
        and atom.get("scope") == proposal.scope
    )


def _eligible(request: Any, verify_decision: Any) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").lower()
    plan = ensure_request_query_plan(request)
    question = request_planning_question(request)
    normalized_type = normalized_answer_type(
        str(plan.answer_type or ""),
        set(_TOKEN_RE.findall(question.lower())),
        question=question,
        numeric_terms=set(),
        causal_intent=False,
    )
    required = [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_verification and slot.role == "support"
    ]
    typed = getattr(verify_decision, "typed_authority", {})
    typed = typed if isinstance(typed, dict) else {}
    return bool(
        domain == "qasper"
        and normalized_type == "free_text"
        and len(required) == 1
        and required[0].statement_kind == "answer_relation"
        and typed.get("state") == "missing"
        and typed.get("reason") == "claim_extension_unverified"
    )


def _item_candidates(
    item: dict[str, Any],
    *,
    question: str,
    relation: str,
) -> list[AnswerRevisionProposal]:
    if _title_only(item):
        return []
    output = []
    for quote, start, end in _sentence_spans(evidence_item_text(item)):
        candidate = _sentence_candidate(
            item,
            quote,
            start,
            end,
            question=question,
            relation=relation,
        )
        if candidate is not None:
            output.append(candidate)
    return output


def _sentence_candidate(
    item: dict[str, Any],
    quote: str,
    start: int,
    end: int,
    *,
    question: str,
    relation: str,
) -> AnswerRevisionProposal | None:
    if _actor(item, quote) != "current_paper":
        return None
    relation_match = _relation_match(quote, relation)
    if relation_match is None or target_relation_is_negated(question, quote):
        return None
    object_span = _object_span(quote, relation_match.end())
    if object_span is None:
        return None
    object_value, _, _ = object_span
    qualifier = _qualifier(question, object_value, quote)
    if qualifier is None:
        return None
    evidence_id = _identity(item)
    if not evidence_id:
        return None
    canonical_base = _canonical_base(item)
    canonical_start = canonical_base + start if canonical_base is not None else None
    canonical_end = canonical_base + end if canonical_base is not None else None
    ref_start = canonical_start if canonical_start is not None else start
    ref_end = canonical_end if canonical_end is not None else end
    evidence_ref = f"{evidence_id}#quote:{ref_start}:{ref_end}"
    source_id, page_label = source_page_locator(item)
    scope = _scope(item)
    return AnswerRevisionProposal(
        revised_answer=object_value,
        canonical_evidence_id=evidence_id,
        evidence_ref=evidence_ref,
        span_id=evidence_ref,
        quote=quote,
        span_start=start,
        span_end=end,
        canonical_start=canonical_start,
        canonical_end=canonical_end,
        actor="current_paper",
        relation=relation,
        object=object_value,
        qualifier=qualifier,
        scope=scope,
        revision_reason="unique_direct_predicate_argument_authority",
        ambiguity_status="unique",
        conflict_status="none",
        source_id=source_id,
        page_label=page_label,
    )


def _unique_direct_authority(
    candidates: list[AnswerRevisionProposal],
) -> AnswerRevisionProposal | None:
    if not candidates:
        return None
    objects = {_normalized(candidate.object) for candidate in candidates}
    if len(objects) != 1:
        return None
    selected_by_span: dict[tuple[str, str], AnswerRevisionProposal] = {}
    for candidate in candidates:
        selected_by_span[
            (candidate.canonical_evidence_id, candidate.evidence_ref)
        ] = candidate
    return min(
        selected_by_span.values(),
        key=lambda candidate: (
            candidate.canonical_evidence_id,
            candidate.evidence_ref,
            candidate.revised_answer,
        ),
    )


def _question_relation(question: str) -> str:
    tokens = {_stem(token) for token in _TOKEN_RE.findall(question.lower())}
    return next((relation for relation in _RELATION_ALIASES if relation in tokens), "")


def _relation_match(quote: str, relation: str) -> re.Match[str] | None:
    aliases = _RELATION_ALIASES.get(relation, ())
    if not aliases:
        return None
    pattern = r"\b(?:" + "|".join(re.escape(value) for value in aliases) + r")\b"
    matches = list(re.finditer(pattern, quote, re.IGNORECASE))
    return matches[0] if len(matches) == 1 else None


def _object_span(quote: str, relation_end: int) -> tuple[str, int, int] | None:
    tail = quote[relation_end:]
    match = re.match(
        r"\s+(?P<object>.+?)(?=\s+(?:as|for)\s+(?:prior|background)\s+knowledge\b)",
        tail,
        re.IGNORECASE,
    )
    if match is None:
        return None
    raw = match.group("object")
    leading = len(raw) - len(raw.lstrip())
    value = raw.strip(" \t,;:")
    if not value or re.search(r"[.!?]", value) or re.search(r"\b(?:and|or)\b", value):
        return None
    start = relation_end + match.start("object") + leading
    end = start + len(value)
    return value, start, end


def _actor(item: dict[str, Any], quote: str) -> str:
    scope = _scope(item)
    if _RELATED_WORK_TERMS.search(scope) or _RELATED_WORK_TERMS.search(quote):
        return "cited_work"
    return "current_paper" if _CURRENT_PAPER_TERMS.search(quote) else "unknown"


def _qualifier(question: str, object_value: str, quote: str) -> str | None:
    expected = {
        match.group(0).lower()
        for value in (question, object_value)
        for match in _QUALIFIER_RE.finditer(value)
    }
    observed_match = _QUALIFIER_RE.search(quote)
    observed = observed_match.group(0).lower() if observed_match else "none"
    if expected and expected != {observed}:
        return None
    return observed


def _scope(item: dict[str, Any]) -> str:
    value = " ".join(
        str(item.get(key) or "").strip()
        for key in ("section_id", "section_title", "section", "heading")
        if str(item.get(key) or "").strip()
    ).lower()
    return value or "document"


def _title_only(item: dict[str, Any]) -> bool:
    kind = " ".join(
        str(item.get(key) or "").lower()
        for key in ("element_type", "modality", "section_id", "section_title")
    )
    return bool(re.search(r"\btitle\b|\bheading\b", kind))


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    output = []
    for match in _SENTENCE_RE.finditer(str(text or "")):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        quote = raw.strip()
        if quote:
            start = match.start() + leading
            output.append((quote, start, start + len(quote)))
    return output


def _identity(item: dict[str, Any]) -> str:
    try:
        return identity_of(item).key
    except ValueError:
        return ""


def _stem(token: str) -> str:
    for relation, aliases in _RELATION_ALIASES.items():
        if token in aliases:
            return relation
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _normalized(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _relations_equivalent(left: Any, right: Any) -> bool:
    left_value = _normalized(left)
    right_value = _normalized(right)
    return bool(
        left_value == right_value
        or _stem(left_value) == _stem(right_value)
        or {left_value, right_value} <= {"attribute", "leverage"}
    )


def _ref_is_exact_quote_span(
    value: Any,
    atom: dict[str, Any],
    proposal: AnswerRevisionProposal,
) -> bool:
    reference = str(value or "")
    if not reference.startswith(f"{proposal.canonical_evidence_id}#quote:"):
        return False
    start = atom.get("canonical_start")
    end = atom.get("canonical_end")
    if not isinstance(start, int) or not isinstance(end, int):
        start = atom.get("span_start")
        end = atom.get("span_end")
    return bool(
        isinstance(start, int)
        and isinstance(end, int)
        and reference == f"{proposal.canonical_evidence_id}#quote:{start}:{end}"
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _canonical_base(item: dict[str, Any]) -> int | None:
    return next(
        (
            value
            for value in (
                _optional_int(item.get("canonical_start")),
                _optional_int(item.get("chunk_start")),
            )
            if value is not None
        ),
        None,
    )
