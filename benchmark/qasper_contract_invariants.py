from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.evidence_locators import normalized_source_page_locators

from .metrics import is_abstention_answer
from .qasper_boolean_scope import scope_valid_support_items
from .qasper_deterministic_support import deterministic_support_ids


def qasper_contract_metric_values(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    *,
    cited: list[dict[str, Any]],
    contract_items: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        **_answerability_metrics(prediction, metadata),
        **_citation_support_metrics(
            prediction,
            metadata,
            cited,
            contract_items=contract_items,
        ),
    }


def _answerability_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, float | None]:
    trace = metadata.get("qasper_answerability")
    if not isinstance(trace, dict):
        return _empty_answerability_metrics()
    candidate = str(trace.get("candidate_for_answerability") or "")
    answer = _final_answer(prediction)
    scope_violation = bool(
        _answer_type(prediction) == "boolean"
        and answer
        and not is_abstention_answer(answer)
        and str(trace.get("boolean_scope_valid") or "").lower() == "false"
    )
    return {
        "abstention_candidate_sent_as_semantic_answer_count": float(
            bool(candidate and is_abstention_answer(candidate))
        ),
        "verifier_required_evidence_coverage": _optional_float(
            trace.get("verifier_required_evidence_coverage")
        ),
        "answerable_false_abstention_count": float(
            _gold_is_answerable(prediction) and is_abstention_answer(answer)
        ),
        "boolean_scope_violation_count": float(scope_violation),
        "wrong_polarity_count": float(_wrong_boolean_polarity(prediction, answer)),
    }


def _citation_support_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    cited: list[dict[str, Any]],
    *,
    contract_items: list[dict[str, Any]],
) -> dict[str, float]:
    verified = _verified_support_items(metadata, contract_items)
    verified_aliases = set().union(*(exact_evidence_aliases(item) for item in verified))
    verified_locators = set().union(
        *(normalized_source_page_locators(item) for item in verified)
    )
    support_violations = sum(
        _citation_lacks_claim_support(
            item,
            verified_aliases=verified_aliases,
            verified_locators=verified_locators,
        )
        for item in cited
    )
    answer = _final_answer(prediction)
    valid_scope_ids = {
        identity_of(item).key
        for item in _scope_valid_citations(prediction, answer, cited)
    }
    scope_violations = sum(
        identity_of(item).key not in valid_scope_ids for item in cited
    )
    nonminimal = (
        max(0, len(cited) - 1)
        if _answer_type(prediction) == "boolean" and not is_abstention_answer(answer)
        else 0
    )
    return {
        "citation_claim_support_violation_count": float(support_violations),
        "citation_scope_violation_count": float(scope_violations),
        "citation_nonminimal_count": float(nonminimal),
    }


def _citation_lacks_claim_support(
    item: dict[str, Any],
    *,
    verified_aliases: set[str],
    verified_locators: set[tuple[str, str]],
) -> bool:
    if exact_evidence_aliases(item) & verified_aliases:
        return False
    if identity_of(item).kind not in {"page", "source"}:
        return True
    return not bool(normalized_source_page_locators(item) & verified_locators)


def _verified_support_items(
    metadata: dict[str, Any],
    contract_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = unambiguous_evidence_alias_lookup(contract_items)
    output: list[dict[str, Any]] = []
    by_claim = metadata.get("verified_claim_support_by_claim")
    if isinstance(by_claim, dict):
        for values in by_claim.values():
            for value in values or []:
                item = value if isinstance(value, dict) else lookup.get(str(value))
                if item is not None:
                    output.append(item)
    output.extend(
        item
        for item in metadata.get("verified_claim_support_evidence") or []
        if isinstance(item, dict)
    )
    return output


def _scope_valid_citations(
    prediction: dict[str, Any],
    answer: str,
    cited: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if _answer_type(prediction) != "boolean" or is_abstention_answer(answer):
        return cited
    metadata = prediction.get("evidence_metadata")
    trace = metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
    support_ids = deterministic_support_ids(trace) if isinstance(trace, dict) else set()
    if support_ids:
        return [item for item in cited if identity_of(item).key in support_ids]
    return scope_valid_support_items(
        str(prediction.get("question") or ""),
        answer,
        cited,
    )


def _empty_answerability_metrics() -> dict[str, float | None]:
    return {
        "abstention_candidate_sent_as_semantic_answer_count": 0.0,
        "verifier_required_evidence_coverage": None,
        "answerable_false_abstention_count": 0.0,
        "boolean_scope_violation_count": 0.0,
        "wrong_polarity_count": 0.0,
    }


def _gold_is_answerable(prediction: dict[str, Any]) -> bool:
    return any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in prediction.get("gold_answers") or []
    )


def _wrong_boolean_polarity(
    prediction: dict[str, Any],
    answer: str,
) -> bool:
    if _answer_type(prediction) != "boolean":
        return False
    predicted = _boolean_polarity(answer)
    gold = {
        polarity
        for value in prediction.get("gold_answers") or []
        if (polarity := _boolean_polarity(str(value)))
    }
    return bool(predicted and len(gold) == 1 and predicted not in gold)


def _boolean_polarity(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "true"}:
        return "yes"
    if normalized in {"no", "false"}:
        return "no"
    return ""


def _final_answer(prediction: dict[str, Any]) -> str:
    return str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )


def _answer_type(prediction: dict[str, Any]) -> str:
    return str(prediction.get("answer_type") or "").strip().lower()


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
