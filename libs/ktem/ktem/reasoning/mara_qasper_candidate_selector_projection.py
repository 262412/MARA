from __future__ import annotations

import hashlib
import re
from typing import Any

from ktem.docqa.question_proposition import build_question_proposition

from .mara_qasper_candidate_evidence import candidate_selector_options_with_trace
from .mara_qasper_candidate_identity import candidate_digest
from .mara_qasper_semantic_pack import prepare_qasper_canonical_records_with_trace
from .mara_semantic_proposition_packing import SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS
from .mara_semantic_proposition_span_selectors import canonical_span_selector_projection

_CANDIDATE_SELECTORS_PER_RECORD = 4


def prioritized_candidate_prompt_evidence(
    evidence: list[dict[str, Any]],
    question: str,
) -> list[dict[str, Any]]:
    projections: list[dict[str, Any]] = []
    for record in evidence:
        source_text = str(
            record.get("candidate_source_text") or record.get("text") or ""
        )
        text_start = int(record.get("candidate_source_text_start") or 0)
        canonical_start = record.get("canonical_start")
        canonical_start = canonical_start if isinstance(canonical_start, int) else None
        raw_selectors, span_projection = canonical_span_selector_projection(
            str(record.get("label") or ""),
            source_text,
            text_start,
            canonical_start,
            selector_max_chars=SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
        )
        projected = {
            **record,
            "text": source_text,
            "text_start": text_start,
            "selectors": raw_selectors,
        }
        eligible, eligibility_decisions = candidate_selector_options_with_trace(
            projected,
            question=question,
        )
        projections.append(
            {
                "record": projected,
                "raw_selectors": raw_selectors,
                "span_projection": span_projection,
                "eligible_options": eligible,
                "eligibility_decisions": eligibility_decisions,
            }
        )

    output: list[dict[str, Any]] = []
    for projection in projections:
        selected_plan_refs, canonical_refs = _record_canonical_priorities(
            projection,
            question,
        )
        options, proposition_bearing_refs = _prioritized_proposition_bearing_options(
            projection["eligible_options"],
            selected_plan_refs=selected_plan_refs,
            canonical_refs=canonical_refs,
        )
        projected = projection["record"]
        projected["selectors"] = _candidate_selectors_from_options(options)
        projected[
            "candidate_selector_projection_trace"
        ] = _candidate_selector_projection_trace(
            projection["raw_selectors"],
            projection["eligible_options"],
            options,
            span_projection=projection["span_projection"],
            eligibility_decisions=projection["eligibility_decisions"],
            proposition_bearing_refs=proposition_bearing_refs,
        )
        output.append(projected)
    return output


def _record_canonical_priorities(
    projection: dict[str, Any],
    question: str,
) -> tuple[list[str], list[str]]:
    """Classify spans before the per-record selector cap is applied."""

    _records, trace = prepare_qasper_canonical_records_with_trace(
        question,
        [
            {
                **projection["record"],
                "selectors": _candidate_selectors_from_options(
                    projection["eligible_options"]
                ),
            }
        ],
    )
    object_contribution_refs = [
        str(option.get("evidence_ref") or "")
        for option in projection["eligible_options"]
        if _cross_record_object_contribution(option, question)
    ]
    return (
        list(trace.get("selected_plan_refs") or []),
        list(
            dict.fromkeys(
                [
                    *(trace.get("selector_universe_refs") or []),
                    *object_contribution_refs,
                ]
            )
        ),
    )


def _cross_record_object_contribution(option: dict[str, Any], question: str) -> bool:
    hints = set(option.get("slot_hints") or [])
    if "object" not in hints or option.get("relation_bearing") is not True:
        return False
    if (
        "predicate" in hints
        and "actor" not in hints
        and option.get("local_relation_state") == "affirmative_assertion"
    ):
        return True
    object_surface = build_question_proposition(question).object_surface
    components = [
        value.strip().casefold()
        for value in re.split(r"\band\b", object_surface, flags=re.IGNORECASE)
        if value.strip()
    ]
    text = str(option.get("text") or "").casefold()
    return (
        len(components) > 1
        and "actor" in hints
        and "predicate" not in hints
        and any(component in text for component in components)
    )


def _candidate_selectors_from_options(
    options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "selector_id": option["evidence_ref"],
            "text": option["text"],
            "span_start": option["span_start"],
            "span_end": option["span_end"],
        }
        for option in options
    ]


def _prioritized_proposition_bearing_options(
    eligible_options: list[dict[str, Any]],
    *,
    selected_plan_refs: list[str],
    canonical_refs: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    eligible_refs = {
        str(option.get("evidence_ref") or "") for option in eligible_options
    }
    mandatory_refs = [ref for ref in selected_plan_refs if ref in eligible_refs]
    if len(mandatory_refs) > _CANDIDATE_SELECTORS_PER_RECORD:
        raise ValueError("candidate_plan_exceeds_record_selector_limit")
    proposition_bearing_refs = list(
        dict.fromkeys(
            [
                *mandatory_refs,
                *(ref for ref in canonical_refs if ref in eligible_refs),
            ]
        )
    )
    selected_ref_set = set(proposition_bearing_refs[:_CANDIDATE_SELECTORS_PER_RECORD])
    selected_options = [
        option
        for option in eligible_options
        if str(option.get("evidence_ref") or "") in selected_ref_set
    ]
    return selected_options, proposition_bearing_refs


def _candidate_selector_projection_trace(
    raw_selectors: list[dict[str, Any]],
    eligible_options: list[dict[str, Any]],
    selected_options: list[dict[str, Any]],
    *,
    span_projection: dict[str, Any],
    eligibility_decisions: list[dict[str, Any]],
    proposition_bearing_refs: list[str],
) -> dict[str, Any]:
    eligible_ranks = {
        str(option.get("evidence_ref") or ""): rank
        for rank, option in enumerate(eligible_options, start=1)
    }
    selected_refs = [
        str(option.get("evidence_ref") or "") for option in selected_options
    ]
    selected = set(selected_refs)
    proposition_bearing = set(proposition_bearing_refs)
    eligibility_by_index = {
        int(decision.get("source_selector_index") or 0): decision
        for decision in eligibility_decisions
    }
    decisions = [
        _candidate_selector_decision(
            selector,
            eligibility=eligibility_by_index.get(index, {}),
            eligible_rank=eligible_ranks.get(str(selector.get("selector_id") or "")),
            selected=str(selector.get("selector_id") or "") in selected,
            proposition_bearing=(
                str(selector.get("selector_id") or "") in proposition_bearing
            ),
        )
        for index, selector in enumerate(raw_selectors, start=1)
    ]
    return {
        "contract_id": "qasper_candidate_selector_projection.v1",
        "complete": True,
        "input_selector_count": len(raw_selectors),
        "eligible_selector_count": len(eligible_options),
        "selected_selector_count": len(selected_options),
        "decision_count": len(decisions),
        "selected_selector_refs": selected_refs,
        "proposition_bearing_selector_refs": proposition_bearing_refs,
        "decisions_digest": candidate_digest(decisions),
        "span_projection": span_projection,
        "decisions": decisions,
    }


def _candidate_selector_decision(
    selector: dict[str, Any],
    *,
    eligibility: dict[str, Any],
    eligible_rank: int | None,
    selected: bool,
    proposition_bearing: bool,
) -> dict[str, Any]:
    selector_id = str(selector.get("selector_id") or "")
    identity = {
        "selector_id": selector_id,
        "span_start": selector.get("span_start"),
        "span_end": selector.get("span_end"),
        "text": str(selector.get("text") or ""),
    }
    return {
        "selector_id": selector_id,
        "selector_identity_digest": candidate_digest(identity),
        "span_start": selector.get("span_start"),
        "span_end": selector.get("span_end"),
        "text_digest": hashlib.sha256(
            str(selector.get("text") or "").encode("utf-8")
        ).hexdigest(),
        "eligible_rank": eligible_rank,
        "eligibility_reason": str(eligibility.get("reason") or ""),
        "selected": selected,
        "decision": (
            "selected_for_canonical_projection"
            if selected
            else "not_proposition_bearing"
            if eligible_rank is not None and not proposition_bearing
            else "candidate_selector_limit"
            if eligible_rank is not None
            else str(eligibility.get("reason") or "semantic_projection_filtered")
        ),
    }
