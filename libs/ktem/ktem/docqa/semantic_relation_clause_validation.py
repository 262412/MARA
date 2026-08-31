from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_context import normalized_object_tokens
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation
from .canonical_proposition_evidence_constraint import semantic_constraint_observation
from .frozen_semantic_relation_projection import (  # noqa: F401 - compatibility re-export
    LOCAL_SEMANTIC_RELATION_CONSTRAINT,
    frozen_semantic_relation_analyses,
)
from .frozen_semantic_relation_projection import (
    frozen_semantic_relation_evidence_set_constraint as _frozen_semantic_relation_evidence_set_constraint,
)
from .frozen_semantic_relation_projection import (  # noqa: F401 - compatibility re-export
    premise_slot_evidence_for_audit,
)
from .qasper_frozen_slot_evidence import verified_frozen_object_span
from .question_proposition import (
    QuestionProposition,
    applicable_proposition_evidence_slots,
)
from .semantic_relation_clause_lexical import ASSERTIVE_VERB_RE as _ASSERTIVE_VERB_RE
from .semantic_relation_clause_lexical import (
    SEMANTIC_SCAFFOLD_TOKENS as _SEMANTIC_SCAFFOLD_TOKENS,
)
from .semantic_relation_clause_lexical import actor_span as _actor_span
from .semantic_relation_clause_lexical import (
    canonical_semantic_token as _canonical_semantic_token,
)
from .semantic_relation_clause_lexical import clause_spans as _clause_spans
from .semantic_relation_clause_lexical import (
    contextual_predicate_span as _contextual_predicate_span,
)
from .semantic_relation_clause_lexical import (
    direct_relation_negated as _direct_relation_negated,
)
from .semantic_relation_clause_lexical import literal_span as _literal_span
from .semantic_relation_clause_lexical import meta_scoped as _is_meta_scoped
from .semantic_relation_clause_lexical import object_span as _object_span
from .semantic_relation_clause_lexical import predicate_spans as _predicate_spans
from .semantic_relation_clause_lexical import (
    semantic_content_token_set as _semantic_content_token_set,
)
from .semantic_relation_constraint_projection import (
    legacy_constraint_projection as _legacy_constraint_projection,
)


def semantic_relation_clause_analysis(
    premise: Mapping[str, Any],
    proposition: QuestionProposition,
) -> dict[str, Any]:
    """Resolve declared proposition slots to exact local relation spans.

    The result is model-independent. It describes what the selected quote can
    establish locally; it does not infer joint entailment for the model.
    """

    quote = str(premise.get("quote") or "")
    declared_slots = _declared_slots(premise)
    required_object_tokens = _semantic_content_token_set(proposition.object_surface)
    clauses = [
        _clause_analysis(
            quote,
            start,
            end,
            index=index,
            declared_slots=declared_slots,
            proposition=proposition,
            required_object_tokens=required_object_tokens,
        )
        for index, (start, end) in enumerate(_clause_spans(quote), start=1)
    ]
    selected = max(clauses, key=_clause_score, default=_empty_clause())
    status = _analysis_status(selected, clauses, declared_slots)
    binding_validity = dict(selected.get("slot_binding_validity") or {})
    slot_evidence = {
        slot: dict(span)
        for slot, span in selected.get("slot_evidence", {}).items()
        if slot in declared_slots and binding_validity.get(slot) is True
    }
    if frozen_object_span := verified_frozen_object_span(
        premise,
        proposition,
        declared_slots=declared_slots,
    ):
        slot_evidence["object"] = frozen_object_span
    fully_bound = bool(
        declared_slots
        and set(slot_evidence) == set(declared_slots)
        and selected.get("slot_bindings_valid") is True
        and selected.get("relation_bearing") is True
        and status in {"affirmative_assertion", "explicit_contradiction"}
    )
    payload = {
        "contract_id": LOCAL_SEMANTIC_RELATION_CONSTRAINT,
        "status": status,
        "evidence_relation": _status_evidence_relation(status),
        "independent_from_models": True,
        "method": "exact_clause_slot_span_and_local_scope",
        "quote_digest": _digest(quote),
        "declared_proposition_slots": declared_slots,
        "joint_relation_clause_bound": fully_bound,
        "selected_clause_ref": str(selected.get("clause_ref") or ""),
        "slot_evidence": slot_evidence,
        "required_object_tokens": sorted(required_object_tokens),
        "covered_object_tokens": list(selected.get("object_tokens_covered") or []),
        "target_relation_present": bool(selected.get("target_relation_present")),
        "relation_bearing": bool(selected.get("relation_bearing")),
        "meta_scope": bool(selected.get("meta_scope")),
        "direct_relation_negated": selected.get("direct_relation_negated"),
        "clauses": clauses,
    }
    payload["analysis_digest"] = _digest(payload)
    return payload


def locally_allowed_proposition_slots(
    quote: str,
    proposition: QuestionProposition,
) -> tuple[str, ...]:
    """Return exact slots a selector may declare before the verifier is called."""

    analysis, observed = _locally_observed_slots(quote, proposition)
    if (
        analysis.get("relation_bearing") is not True
        or analysis.get("meta_scope") is True
    ):
        return ()
    return observed


def locally_observed_proposition_slots(
    quote: str,
    proposition: QuestionProposition,
) -> tuple[str, ...]:
    """Return exact local slot observations, including companion noun spans."""

    analysis, observed = _locally_observed_slots(quote, proposition)
    return () if analysis.get("meta_scope") is True else observed


def _locally_observed_slots(
    quote: str,
    proposition: QuestionProposition,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    applicable = applicable_proposition_evidence_slots(proposition)
    analysis = semantic_relation_clause_analysis(
        {"quote": quote, "binds_proposition_slots": list(applicable)},
        proposition,
    )
    evidence = dict(analysis.get("slot_evidence") or {})
    observed = tuple(slot for slot in applicable if slot in evidence)
    return analysis, observed


def semantic_relation_evidence_set_constraint(
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    verdict: str,
    *,
    auditor_relationship: str,
    canonical_plan_projection: Any | None = None,
) -> dict[str, Any]:
    if canonical_plan_projection is not None:
        return _frozen_semantic_relation_evidence_set_constraint(
            canonical_plan_projection,
            verdict,
            auditor_relationship=auditor_relationship,
        )
    analyses = [
        semantic_relation_clause_analysis(premise, proposition) for premise in premises
    ]
    (
        required_slots,
        bound_slots,
        required_object_tokens,
        covered_object_tokens,
    ) = semantic_constraint_observation(
        analyses,
        proposition,
    )
    (
        bound_slots,
        covered_object_tokens,
        reason,
        no_evidence_semantics,
        support_evidence_binding_complete,
    ) = _legacy_constraint_projection(
        premises,
        proposition,
        verdict,
        analyses=analyses,
        required_slots=required_slots,
        bound_slots=bound_slots,
        required_object_tokens=required_object_tokens,
        covered_object_tokens=covered_object_tokens,
    )
    payload = {
        "contract_id": LOCAL_SEMANTIC_RELATION_CONSTRAINT,
        "status": "passed" if not reason else "rejected",
        "reason": reason,
        "verdict": str(verdict or ""),
        "expected_evidence_relation": (
            "proposition_support" if verdict == "yes" else "explicit_contradiction"
        ),
        "auditor_relationship": str(auditor_relationship or ""),
        "independent_from_models": True,
        "correlated_model_guard_applied": auditor_relationship
        in {"same_instance", "distinct_instance_same_model"},
        "model_call_count": 0,
        "method": "exact_clause_slot_span_and_local_scope",
        "required_proposition_slots": required_slots,
        "bound_proposition_slots": bound_slots,
        "required_object_tokens": required_object_tokens,
        "covered_object_tokens": covered_object_tokens,
        "uncovered_object_tokens": sorted(
            set(required_object_tokens) - set(covered_object_tokens)
        ),
        "local_relation_states": [
            str(analysis.get("status") or "unbound") for analysis in analyses
        ],
        "premise_analyses": analyses,
        "qasper_no_evidence_semantics": no_evidence_semantics,
        "support_evidence_binding_complete": support_evidence_binding_complete,
    }
    payload["constraint_digest"] = _digest(payload)
    return payload


def validated_argument_tokens(
    question: str,
    analysis: Mapping[str, Any],
    required_tokens: Sequence[str],
) -> tuple[str, ...]:
    """Project coverage only from locally valid, exact slot evidence."""

    if analysis.get("joint_relation_clause_bound") is not True or analysis.get(
        "status"
    ) not in {"affirmative_assertion", "explicit_contradiction"}:
        return ()
    if tuple(required_tokens) == ("complete_proposition",):
        return ("complete_proposition",)
    evidence_text = " ".join(
        str(value.get("text") or "")
        for value in dict(analysis.get("slot_evidence") or {}).values()
        if isinstance(value, Mapping)
    )
    relation = primary_boolean_relation(question)
    asserted = {
        _canonical_semantic_token(token)
        for token in normalized_object_tokens(
            evidence_text,
            _relation_surface_tokens(relation),
        )
    }
    asserted.update(_semantic_content_token_set(evidence_text))
    asserted.discard("")
    return tuple(sorted(set(required_tokens) & asserted))


def semantic_required_argument_tokens(question: str) -> tuple[str, ...]:
    """Return the deterministic argument contract for semantic authority."""

    relation = primary_boolean_relation(question) or "entails"
    tokens = {
        _canonical_semantic_token(token)
        for token in _question_argument_tokens(
            question,
            _relation_surface_tokens(relation),
        )
    }
    tokens -= _SEMANTIC_SCAFFOLD_TOKENS | {""}
    return tuple(sorted(tokens)) or ("complete_proposition",)


def semantic_slot_evidence_projection(
    analysis: Mapping[str, Any],
    *,
    premise_ref: str,
    span_base: int,
) -> dict[str, dict[str, Any]]:
    """Project quote-local slot spans to exact authority-level references."""

    output: dict[str, dict[str, Any]] = {}
    for slot, raw_span in dict(analysis.get("slot_evidence") or {}).items():
        if not isinstance(raw_span, Mapping):
            continue
        start = int(raw_span.get("span_start") or 0) + span_base
        end = int(raw_span.get("span_end") or 0) + span_base
        clause_start = int(raw_span.get("clause_start") or 0) + span_base
        clause_end = int(raw_span.get("clause_end") or 0) + span_base
        output[str(slot)] = {
            "evidence_ref": f"{premise_ref}#slot:{slot}:{start}:{end}",
            "text": str(raw_span.get("text") or ""),
            "span_start": start,
            "span_end": end,
            "clause_ref": str(raw_span.get("clause_ref") or ""),
            "clause_start": clause_start,
            "clause_end": clause_end,
        }
    return output


def _clause_analysis(
    quote: str,
    start: int,
    end: int,
    *,
    index: int,
    declared_slots: list[str],
    proposition: QuestionProposition,
    required_object_tokens: set[str],
) -> dict[str, Any]:
    clause = quote[start:end]
    predicate_spans = _predicate_spans(clause, proposition.predicate, offset=start)
    contextual_predicate = _contextual_predicate_span(clause, offset=start)
    object_span, object_tokens = _object_span(
        clause,
        proposition.object_surface,
        required_object_tokens,
        offset=start,
    )
    actor_span, actor_matches = _actor_span(clause, proposition, offset=start)
    candidates: dict[str, dict[str, Any] | None] = {
        "actor": actor_span,
        "predicate": predicate_spans[0] if predicate_spans else None,
        "object": object_span,
        "quantifier": _literal_span(clause, proposition.quantifier, offset=start),
    }
    clause_ref = f"C{index}"
    slot_evidence = {
        slot: {
            **span,
            "clause_ref": clause_ref,
            "clause_start": start,
            "clause_end": end,
        }
        for slot in declared_slots
        if (span := candidates.get(slot)) is not None
    }
    predicate_span = predicate_spans[0] if predicate_spans else None
    meta_scope = bool(
        predicate_span and _is_meta_scoped(clause, predicate_span["span_start"] - start)
    )
    relation_negated = (
        _direct_relation_negated(clause, predicate_span["span_start"] - start)
        if predicate_span is not None and not meta_scope
        else None
    )
    if relation_negated is not None and proposition.negated:
        relation_negated = not relation_negated
    binding_validity = {
        "actor": actor_matches,
        "predicate": bool(predicate_spans)
        and _predicate_actor_order_valid(
            proposition,
            actor_span=actor_span,
            predicate_span=predicate_span,
        ),
        "object": bool(required_object_tokens and object_tokens),
        "quantifier": candidates["quantifier"] is not None,
    }
    return {
        "clause_ref": clause_ref,
        "text": clause,
        "span_start": start,
        "span_end": end,
        "slot_evidence": slot_evidence,
        "slot_binding_validity": {
            slot: binding_validity[slot] for slot in declared_slots
        },
        "slot_bindings_valid": all(binding_validity[slot] for slot in declared_slots),
        "object_tokens_required": sorted(required_object_tokens),
        "object_tokens_covered": sorted(object_tokens),
        "target_relation_present": bool(predicate_spans),
        "relation_bearing": bool(
            predicate_spans or contextual_predicate or _ASSERTIVE_VERB_RE.search(clause)
        ),
        "meta_scope": meta_scope,
        "direct_relation_negated": relation_negated,
    }


def _analysis_status(
    selected: Mapping[str, Any],
    clauses: list[dict[str, Any]],
    declared_slots: list[str],
) -> str:
    selected_slots = set(selected.get("slot_evidence") or {})
    selected_complete = set(declared_slots) == selected_slots
    direct_complete = bool(
        selected_complete
        and selected.get("slot_bindings_valid") is True
        and selected.get("relation_bearing") is True
    )
    missing_object_tokens = set(selected.get("object_tokens_required") or []) - set(
        selected.get("object_tokens_covered") or []
    )
    if missing_object_tokens and any(
        value.get("clause_ref") != selected.get("clause_ref")
        and value.get("meta_scope") is True
        and value.get("target_relation_present") is True
        and bool(missing_object_tokens & set(value.get("object_tokens_covered") or []))
        for value in clauses
    ):
        return "mention_only"
    if direct_complete and selected.get("meta_scope") is True:
        return "mention_only"
    if direct_complete and selected.get("target_relation_present") is True:
        return (
            "explicit_contradiction"
            if selected.get("direct_relation_negated") is True
            else "affirmative_assertion"
        )
    if direct_complete:
        return "affirmative_assertion"
    if any(
        value.get("meta_scope") is True
        and value.get("target_relation_present") is True
        and value.get("object_tokens_covered")
        for value in clauses
    ):
        return "mention_only"
    return "unbound"


def _predicate_actor_order_valid(
    proposition: QuestionProposition,
    *,
    actor_span: Mapping[str, Any] | None,
    predicate_span: Mapping[str, Any] | None,
) -> bool:
    if proposition.predicate not in {"be_collection_of", "be_subject_to"}:
        return True
    if actor_span is None or predicate_span is None:
        return False
    predicate_text = str(predicate_span.get("text") or "").casefold()
    if predicate_text not in {"is", "are", "was", "were", "be"}:
        return True
    return int(actor_span.get("span_end") or 0) <= int(
        predicate_span.get("span_start") or -1
    )


def _clause_score(value: Mapping[str, Any]) -> tuple[int, int, int, int, int]:
    slots = dict(value.get("slot_evidence") or {})
    return (
        sum(
            bool(valid)
            for valid in dict(value.get("slot_binding_validity") or {}).values()
        ),
        len(slots),
        len(value.get("object_tokens_covered") or []),
        int(value.get("target_relation_present") is True),
        int(value.get("meta_scope") is not True),
    )


def _declared_slots(premise: Mapping[str, Any]) -> list[str]:
    raw = premise.get("binds_proposition_slots")
    return [str(slot) for slot in raw or [] if isinstance(slot, str)]


def _status_evidence_relation(status: str) -> str:
    return {
        "affirmative_assertion": "proposition_support",
        "explicit_contradiction": "explicit_contradiction",
    }.get(status, "undetermined")


def _empty_clause() -> dict[str, Any]:
    return {
        "clause_ref": "",
        "slot_evidence": {},
        "slot_binding_validity": {},
        "slot_bindings_valid": False,
        "object_tokens_covered": [],
        "target_relation_present": False,
        "relation_bearing": False,
        "meta_scope": False,
        "direct_relation_negated": None,
    }


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
