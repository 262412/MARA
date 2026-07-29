from __future__ import annotations

from typing import Any

from ktem.docqa.calculation_claim_verification import calculation_claim_result
from ktem.docqa.controller import evaluate_retrieval_quality
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle


def _cell() -> dict[str, object]:
    return {
        "source_id": "report",
        "page_label": "60",
        "table_id": "cash-flow",
        "cell_id": "capex-2018",
        "evidence_level": "cell",
        "row_label": "Purchases of property, plant and equipment",
        "column_label": "2018",
        "period": "2018",
        "value": "-1577",
        "text": "Purchases of property, plant and equipment (1,577)",
    }


def _typed_metadata(*, complete: bool = True, formula_status: str = "supported"):
    cell = _cell()
    cell_identity = identity_of(cell).key
    required = ["operand:capital_expenditure:2018"]
    return {
        "evidence": [cell],
        "query_plan": {
            "constraints": {
                "verification_domain": "finance",
                "finance_formula_status": formula_status,
            },
            "evidence_slots": [
                {
                    "slot_id": required[0],
                    "role": "operand",
                    "required_for_execution": True,
                    "status": "filled" if complete else "missing",
                    "evidence_ids": [cell_identity] if complete else [],
                }
            ],
        },
        "finance_numeric_trace": {
            "attempt_status": "executed" if complete else "verification_failed",
            "calculation_plan": {
                "answer_unit": "currency",
                "answer_scale": "million",
            },
            "calculation_verification": {
                "valid": complete,
                "required_slot_ids": required,
                "verified_required_slot_ids": required if complete else [],
                "citation_ids": [cell_identity] if complete else [],
            },
            "calculation_execution": {
                "status": "ok" if complete else "error",
                "value": "-1577" if complete else None,
                "citation_ids": [cell_identity] if complete else [],
            },
        },
        "missing_required_slot_count": 0 if complete else 1,
    }


def test_verified_typed_execution_overrides_legacy_cash_flow_text_gate():
    metadata = _typed_metadata()

    decision = evaluate_retrieval_quality(
        "doc_text",
        metadata,
        prompt="What was capital expenditure in 2018?",
        verification_domain="finance",
        origin="benchmark",
    )

    assert decision.status == "good"
    assert metadata["typed_adequacy_status"] == "good"
    assert metadata["heuristic_adequacy_status"] == "ambiguous"
    assert metadata["final_adequacy_status"] == "good"
    assert metadata["adequacy_decision_authority"] == "typed_calculation"


def test_verified_typed_execution_cannot_be_abstained_by_missing_phrase():
    metadata = _typed_metadata()

    decision = evaluate_retrieval_quality(
        "doc_text",
        metadata,
        prompt="What was capital expenditure in 2018?",
        verification_domain="finance",
    )

    assert decision.retry is False
    assert metadata["heuristic_overridden"] is True


def test_incomplete_typed_execution_does_not_override_adequacy():
    metadata = _typed_metadata(complete=False)

    decision = evaluate_retrieval_quality(
        "doc_text",
        metadata,
        prompt="What was capital expenditure in 2018?",
        verification_domain="finance",
    )

    assert decision.status != "good"
    assert metadata["adequacy_decision_authority"] == "query_plan"
    assert metadata["heuristic_overridden"] is False


def test_unknown_formula_still_uses_general_adequacy():
    metadata = _typed_metadata(formula_status="unsupported")

    decision = evaluate_retrieval_quality(
        "doc_text",
        metadata,
        prompt="What was the invented productivity turnover in 2018?",
        verification_domain="finance",
    )

    assert decision.status == "good"
    assert metadata["typed_adequacy_status"] == "not_applicable"
    assert metadata["adequacy_decision_authority"] == "general_heuristic"


def test_heuristic_override_is_recorded_in_trace():
    metadata = _typed_metadata()

    evaluate_retrieval_quality(
        "doc_text",
        metadata,
        prompt="What was capital expenditure in 2018?",
        verification_domain="finance",
    )

    assert metadata["heuristic_override_reason"] == (
        "verified_typed_execution_supersedes_legacy_text_heuristic"
    )


def _calculation_bundle(
    raw_value: str,
    *,
    answer_unit: str = "percent",
    rounding_places: int | None = None,
    raw_result_unit: str = "",
) -> EvidenceBundle:
    cell = _cell()
    cell_identity = identity_of(cell).key
    plan: dict[str, Any] = {
        "answer_unit": answer_unit,
        "answer_scale": "",
        "raw_result_unit": raw_result_unit,
    }
    if rounding_places is not None:
        plan["rounding_places"] = rounding_places
    return EvidenceBundle(
        route="doc_text",
        items=[cell],
        metadata={
            "finance_numeric_trace": {
                "calculation_plan": plan,
                "calculation_verification": {
                    "valid": True,
                    "required_slot_ids": ["operand:value"],
                    "verified_required_slot_ids": ["operand:value"],
                },
                "calculation_execution": {
                    "status": "ok",
                    "value": raw_value,
                    "citation_ids": [cell_identity],
                },
            }
        },
    )


def test_rounding_one_decimal_accepts_65_387_as_65_4():
    bundle = _calculation_bundle("65.387")

    result = calculation_claim_result(
        bundle,
        "The percentage change was 65.4%.",
        ["The percentage change was 65.4%."],
        domain="finance",
        prompt="What was the percentage change, rounded to one decimal place?",
    )

    assert result is not None and result.status == "supported"
    assert bundle.metadata["calculation_result_comparison"]["decimal_places"] == 1


def test_rounding_one_decimal_accepts_1_9144_as_1_9():
    result = calculation_claim_result(
        _calculation_bundle("1.9144"),
        "The percentage change was 1.9%.",
        ["The percentage change was 1.9%."],
        domain="finance",
        prompt="Give the answer to one decimal place.",
    )

    assert result is not None and result.status == "supported"


def test_rounding_two_decimals_accepts_24_2579_as_24_26():
    result = calculation_claim_result(
        _calculation_bundle("24.2579"),
        "The result was 24.26%.",
        ["The result was 24.26%."],
        domain="finance",
        prompt="Round the result to two decimal places.",
    )

    assert result is not None and result.status == "supported"


def test_rounding_one_decimal_rejects_65_5():
    result = calculation_claim_result(
        _calculation_bundle("65.387"),
        "The percentage change was 65.5%.",
        ["The percentage change was 65.5%."],
        domain="finance",
        prompt="Round to one decimal place.",
    )

    assert result is not None and result.status == "contradicted"


def test_fraction_is_normalized_to_percent_before_quantization():
    result = calculation_claim_result(
        _calculation_bundle("0.65387", raw_result_unit="fraction"),
        "The percentage change was 65.4%.",
        ["The percentage change was 65.4%."],
        domain="finance",
        prompt="Round the percentage to one decimal place.",
    )

    assert result is not None and result.status == "supported"


def test_question_precision_overrides_rendered_fallback():
    bundle = _calculation_bundle("65.387", rounding_places=2)
    result = calculation_claim_result(
        bundle,
        "The result was 65.4%.",
        ["The result was 65.4%."],
        domain="finance",
        prompt="Round to one decimal place.",
    )

    assert result is not None and result.status == "supported"
    assert bundle.metadata["calculation_result_comparison"]["precision_source"] == (
        "question"
    )


def test_formula_precision_used_when_question_has_no_precision():
    bundle = _calculation_bundle("24.2579", rounding_places=2)
    result = calculation_claim_result(
        bundle,
        "The result was 24.26%.",
        ["The result was 24.26%."],
        domain="finance",
        prompt="What was the result?",
    )

    assert result is not None and result.status == "supported"
    assert bundle.metadata["calculation_result_comparison"]["precision_source"] == (
        "formula_spec"
    )


def test_no_global_tolerance_widening():
    result = calculation_claim_result(
        _calculation_bundle("1000"),
        "The result was 1000.2%.",
        ["The result was 1000.2%."],
        domain="finance",
        prompt="What was the exact result?",
    )

    assert result is not None and result.status == "contradicted"
