from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence import EvidenceBundle, _materialize_execution_cells
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_segment_comparison import finance_segment_comparison_answer
from ktem.docqa.finance_typed_adequacy import ensure_finance_numeric_trace
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan

from benchmark.task_answer_contracts import synchronize_terminal_answer_state


def _page(
    evidence_id: str,
    page_label: str,
    text: str,
    *,
    source_id: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "page_label": page_label,
        "evidence_level": "page",
        "modality": "text",
        "text": text,
    }


def _segment_cell(
    entity: str,
    period: str,
    value: str,
    *,
    table_id: str = "segment-revenue",
) -> dict[str, Any]:
    cell_id = f"{entity.lower().replace(' ', '-')}-{period}"
    return {
        "evidence_id": cell_id,
        "cell_id": cell_id,
        "source_id": "AMD_2022_10K",
        "page_label": "48",
        "table_instance_id": table_id,
        "table_group_id": table_id,
        "evidence_level": "cell",
        "cell_role": "data",
        "row_label": entity,
        "column_label": period,
        "period": period,
        "period_kind": "fiscal_year",
        "value": value,
        "unit": "USD",
        "scale": "million",
        "currency": "USD",
        "statement_kind": "segment_table",
        "financial_scope": "segment",
        "text": f"AMD reporting segment {entity} {period} {value} million.",
    }


def _pepsico_page() -> dict[str, Any]:
    return _page(
        "pepsico-page-2",
        "2",
        (
            "Effective May 26, 2023, PepsiCo terminated the $3,800,000,000 364 day "
            "unsecured revolving credit agreement. On May 26, 2023, PepsiCo entered "
            "into a new $4,200,000,000 364 day unsecured revolving credit agreement "
            "(the 2023 364 Day Credit Agreement). The 2023 364 Day Credit Agreement "
            "enables PepsiCo to borrow up to $4,200,000,000. Effective May 26, 2023, "
            "PepsiCo terminated the $3,800,000,000 five year unsecured revolving credit "
            "agreement. On May 26, 2023, PepsiCo entered into a new $4,200,000,000 five "
            "year unsecured revolving credit agreement (the 2023 Five Year Credit "
            "Agreement). The 2023 Five Year Credit Agreement enables PepsiCo to borrow "
            "up to $4,200,000,000."
        ),
        source_id="pepsico",
    )


def _assert_canonical_numeric_state(
    request: Any,
    bundle: EvidenceBundle,
    trace: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> None:
    canonical = trace["authoritative_query_plan"]
    assert (
        bundle.metadata["query_plan"]
        == bundle.metadata["bound_query_plan"]
        == canonical
    )
    assert bundle.metadata["query_plan"]["plan_id"] == canonical["plan_id"]
    assert request.query_plan_id == canonical["plan_id"]
    request_slots = {
        slot["slot_id"]: slot for slot in request.query_plan.as_dict()["evidence_slots"]
    }
    for slot in canonical["evidence_slots"]:
        request_slot = request_slots[slot["slot_id"]]
        for key in (
            "role",
            "entity",
            "metric",
            "period",
            "unit",
            "scale",
            "required_for_execution",
            "required_for_verification",
            "status",
            "evidence_ids",
            "cardinality",
        ):
            assert request_slot[key] == slot.get(key, request_slot[key])
    plan_slots = {
        slot["slot_id"]: slot
        for slot in canonical["evidence_slots"]
        if slot.get("required_for_verification")
    }
    state_slots = {
        state["slot_id"]: state for state in bundle.metadata["verification_slot_states"]
    }
    assert set(state_slots) == set(plan_slots)
    evidence_ids = {identity_of(item).key for item in evidence_items}
    citation_ids = set(trace["calculation_execution"]["citation_ids"])
    for state in state_slots.values():
        assert state["status"] == "verified_support"
        assert state["evidence_ids"]
        assert set(state["evidence_ids"]) <= evidence_ids
        assert set(state["evidence_ids"]) <= citation_ids


def test_00882_local_scale_one_stays_operand_local() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    request = SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
    )
    expanded = _materialize_execution_cells(request, [_pepsico_page()], {})
    bound = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=bound.as_dict())

    assert answer is not None
    assert answer.attempt_status == "executed"
    assert all(
        slot.get("slot_id") != "dimension:scale"
        for slot in answer.authoritative_query_plan.get("evidence_slots", [])
    )
    assert all(
        operand.get("dimension_binding_scope")
        not in {"table", "table_group", "page", "source"}
        for operand in answer.calculation_plan["operands"]
        if operand.get("scale") == "one"
    )
    assert answer.as_trace()["dimension_bindings"] == []


def test_00882_numeric_trace_syncs_one_canonical_plan_and_slot_states() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    request = SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        query_plan_id="stale-plan-id",
        query_plan_state_version=4,
    )
    expanded = _materialize_execution_cells(request, [_pepsico_page()], {})
    bound = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=bound.as_dict())
    assert answer is not None
    trace = answer.as_trace()
    metadata: dict[str, Any] = {
        "finance_numeric_trace": trace,
        "query_plan": {"plan_id": "stale-plan-id", "evidence_slots": []},
        "bound_query_plan": {"plan_id": "stale-plan-id", "evidence_slots": []},
        "verification_slot_states": [
            {
                "slot_id": "stale",
                "status": "verified_support",
                "evidence_ids": ["stale"],
            }
        ],
    }
    bundle = EvidenceBundle(route="text_rag", items=expanded, metadata=metadata)

    ensure_finance_numeric_trace(request, bundle)
    _assert_canonical_numeric_state(request, bundle, trace, expanded)
    assert request.query_plan_state_version == 5

    ensure_finance_numeric_trace(request, bundle)
    assert request.query_plan_state_version == 5


def test_00882_numeric_trace_sync_fails_closed_on_missing_citation() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    request = SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        query_plan_state_version=2,
    )
    expanded = _materialize_execution_cells(request, [_pepsico_page()], {})
    bound = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=bound.as_dict())
    assert answer is not None
    trace = answer.as_trace()
    slot = trace["authoritative_query_plan"]["evidence_slots"][0]
    slot["evidence_ids"] = list(slot["evidence_ids"]) + ["evidence:missing"]
    trace["calculation_execution"]["citation_ids"] = list(
        trace["calculation_execution"]["citation_ids"]
    ) + ["evidence:missing-citation"]
    metadata: dict[str, Any] = {
        "finance_numeric_trace": trace,
        "query_plan": {"plan_id": "stale-plan-id", "evidence_slots": []},
    }
    bundle = EvidenceBundle(route="text_rag", items=expanded, metadata=metadata)

    ensure_finance_numeric_trace(request, bundle)

    assert all(
        state["status"] == "missing" and state["evidence_ids"] == []
        for state in bundle.metadata["verification_slot_states"]
    )
    assert "typed_calculation_support_evidence" not in bundle.metadata
    assert "typed_calculation_citation_ids" not in bundle.metadata


def test_00882_invalid_trace_clears_stale_typed_support() -> None:
    question = (
        "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
        "unsecured revolving credit agreements?"
    )
    request = SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=build_query_plan(
            question,
            answer_type="numeric",
            verification_domain="finance",
        ),
        query_plan_state_version=1,
    )
    expanded = _materialize_execution_cells(request, [_pepsico_page()], {})
    bound = bind_evidence_slots(request.query_plan, expanded)
    answer = finance_numeric_answer(question, expanded, query_plan=bound.as_dict())
    assert answer is not None
    trace = answer.as_trace()
    trace["calculation_verification"]["valid"] = False
    bundle = EvidenceBundle(
        route="text_rag",
        items=expanded,
        metadata={
            "finance_numeric_trace": trace,
            "typed_calculation_support_evidence": list(expanded),
            "typed_calculation_citation_ids": [identity_of(expanded[0]).key],
        },
    )

    ensure_finance_numeric_trace(request, bundle)

    assert all(
        state["status"] == "missing" and state["evidence_ids"] == []
        for state in bundle.metadata["verification_slot_states"]
    )
    assert "typed_calculation_support_evidence" not in bundle.metadata
    assert "typed_calculation_citation_ids" not in bundle.metadata


def test_numeric_trace_without_authoritative_plan_clears_stale_state_atomically() -> None:
    question = "What was PepsiCo's FY2021 capital expenditure amount?"
    plan = build_query_plan(
        question,
        answer_type="numeric",
        verification_domain="finance",
    )
    stale = plan.as_dict()
    stale["state_authority"] = "verified_calculation_plan"
    stale["state_version"] = 3
    stale["evidence_slots"] = [
        {**slot, "status": "verified_support", "evidence_ids": ["stale"]}
        for slot in stale["evidence_slots"]
    ]
    request = SimpleNamespace(
        prompt=question,
        answer_type="numeric",
        verification_domain="finance",
        query_plan=plan,
        query_plan_state_version=3,
    )
    trace = {
        "authoritative_query_plan": {},
        "calculation_verification": {"valid": False},
        "calculation_execution": {"status": "error", "citation_ids": []},
    }
    bundle = EvidenceBundle(
        route="text_rag",
        items=[],
        metadata={
            "finance_numeric_trace": trace,
            "query_plan": stale,
            "bound_query_plan": dict(stale),
            "verification_slot_states": [
                {
                    "slot_id": slot["slot_id"],
                    "status": "verified_support",
                    "evidence_ids": ["stale"],
                }
                for slot in stale["evidence_slots"]
                if slot.get("required_for_verification")
            ],
        },
    )

    ensure_finance_numeric_trace(request, bundle)

    final_plan = bundle.metadata["query_plan"]
    assert final_plan == bundle.metadata["bound_query_plan"]
    assert final_plan["state_authority"] == "unverified_calculation.v1"
    assert all(
        slot["status"] == "missing" and slot["evidence_ids"] == []
        for slot in final_plan["evidence_slots"]
    )
    assert all(
        state["status"] == "missing" and state["evidence_ids"] == []
        for state in bundle.metadata["verification_slot_states"]
    )
    assert all(slot.status == "missing" for slot in request.query_plan.evidence_slots)
    assert request.query_plan_state_version == 4

    ensure_finance_numeric_trace(request, bundle)
    assert request.query_plan_state_version == 4


def test_00563_bound_segment_matrix_has_complete_entity_period_pairs() -> None:
    question = (
        "From FY21 to FY22, excluding Embedded, in which AMD reporting segment did sales "
        "proportionally increase the most?"
    )
    cells = [
        _segment_cell(entity, period, value)
        for entity, values in {
            "Data Center": ("3694", "6043"),
            "Client": ("6887", "6201"),
            "Gaming": ("5607", "6805"),
            "Embedded": ("246", "4552"),
        }.items()
        for period, value in (("2021", values[0]), ("2022", values[1]))
    ]
    plan = build_query_plan(
        question,
        answer_type="extractive",
        verification_domain="finance",
    )

    bound = bind_evidence_slots(plan, cells)
    assert all(slot.status == "filled" for slot in bound.evidence_slots)
    expected_entities = {"Data Center", "Client", "Gaming"}
    for slot in bound.evidence_slots:
        assert slot.period in {"2021", "2022"}
        assert {
            next(
                cell["row_label"]
                for cell in cells
                if identity_of(cell).key == evidence_id
            )
            for evidence_id in slot.evidence_ids
        } == expected_entities
    result = finance_segment_comparison_answer(
        question,
        cells,
        query_plan=bound.as_dict(),
    )

    assert result is not None
    assert result.status == "ok"
    assert result.answer == "Data Center"


def test_02416_wrong_authority_clears_query_plan_and_slot_states_atomically() -> None:
    wrong = {
        "evidence_id": "wrong-pfizer-evidence",
        "source_id": "PFIZER_2021_10K",
        "page_label": "71",
        "evidence_level": "page",
        "text": "Array Therachon Meridian",
    }
    wrong_id = identity_of(wrong).key
    plan = {
        "evidence_slots": [
            {
                "slot_id": "support:primary",
                "role": "support",
                "required_for_verification": True,
                "status": "verified_support",
                "evidence_ids": [wrong_id],
            }
        ],
    }
    bound_plan = {**plan, "state_authority": "verified_calculation_plan"}
    terminal_plan = {**plan, "state_authority": "verified_claim_support.v1"}
    prediction: dict[str, Any] = {
        "predicted_answer": "Array, Therachon, Meridian",
        "answer_for_scoring": "Array, Therachon, Meridian",
        "finance_citation_authority_status": "verified_claim_support",
        "verify_decision": {"status": "supported"},
        "evidence_metadata": {
            "query_plan": plan,
            "bound_query_plan": bound_plan,
            "terminal_query_plan": terminal_plan,
            "verification_slot_states": [
                {
                    "slot_id": "support:primary",
                    "status": "verified_support",
                    "evidence_ids": [wrong_id],
                }
            ],
            "verified_claim_support_evidence": [],
            "selected_evidence": [wrong],
        },
        "evidence_bundle": {
            "items": [wrong],
            "metadata": {
                "query_plan": plan,
                "bound_query_plan": bound_plan,
                "terminal_query_plan": terminal_plan,
                "verification_slot_states": [
                    {
                        "slot_id": "support:primary",
                        "status": "verified_support",
                        "evidence_ids": [wrong_id],
                    }
                ],
                "verified_claim_support_evidence": [],
            },
        },
    }

    assert synchronize_terminal_answer_state(prediction)
    assert prediction["answer_for_scoring"] == "unanswerable"
    for metadata in (
        prediction["evidence_metadata"],
        prediction["evidence_bundle"]["metadata"],
    ):
        for key in ("query_plan", "bound_query_plan", "terminal_query_plan"):
            final_plan = metadata[key]
            assert final_plan["state_authority"] == "abstained.v1"
            assert all(
                slot.get("status") == "missing" and not slot.get("evidence_ids")
                for slot in final_plan.get("evidence_slots", [])
            )
        assert all(
            state.get("status") == "missing" and not state.get("evidence_ids")
            for state in metadata.get("verification_slot_states", [])
        )
