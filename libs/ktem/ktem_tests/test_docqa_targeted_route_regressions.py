from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import EvidenceBundle, build_evidence_bundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.finance_typed_adequacy import ensure_finance_numeric_trace
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan
from ktem.docqa.verification import verify_decision, with_verification_evidence
from ktem.docqa.visual_backends import QwenVLVisualGenerator
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer
from ktem.reasoning.mara_query_planning import understand_query
from ktem.reasoning.mara_visual_answering import route_visual_answer

FINANCE_CCC_QUESTION = (
    "What is the FY2019 cash conversion cycle (CCC) for General Mills? "
    "CCC is defined as: DIO + DSO - DPO. DIO is defined as: 365 * "
    "(average inventory between FY2018 and FY2019) / (FY2019 COGS). "
    "DSO is defined as: 365 * (average accounts receivable between FY2018 "
    "and FY2019) / (FY2019 Revenue). DPO is defined as: 365 * (average "
    "accounts payable between FY2018 and FY2019) / (FY2019 COGS + change "
    "in inventory between FY2018 and FY2019). Round your answer to two "
    "decimal places."
)


def test_finance_ccc_chain_binds_all_operands_and_executes() -> None:
    evidence = _finance_ccc_evidence()
    plan = build_query_plan(
        FINANCE_CCC_QUESTION,
        answer_type="numeric",
        verification_domain="finance",
    )

    assert plan.constraints["finance_formula_status"] == "supported"
    assert {
        (slot.metric, slot.period)
        for slot in plan.evidence_slots
        if slot.role == "operand"
    } == {
        ("inventory", "2018"),
        ("inventory", "2019"),
        ("accounts receivable", "2018"),
        ("accounts receivable", "2019"),
        ("accounts payable", "2018"),
        ("accounts payable", "2019"),
        ("cost of goods sold", "2019"),
        ("net sales", "2019"),
    }

    bound = bind_evidence_slots(plan, evidence)
    assert all(slot.status == "filled" for slot in bound.evidence_slots)

    request = DocQARequest(
        prompt=FINANCE_CCC_QUESTION,
        controller_question=FINANCE_CCC_QUESTION,
        retrieval_query=FINANCE_CCC_QUESTION,
        task_type="numeric",
        verification_domain="finance",
        query_plan=bound,
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=evidence,
        metadata={"query_plan": bound.as_dict()},
    )
    ensure_finance_numeric_trace(request, bundle)

    trace = bundle.metadata["finance_numeric_trace"]
    assert trace["answer"] == "-3.7"
    assert trace["attempt_status"] == "executed"
    assert trace["calculation_verification"]["valid"] is True
    assert trace["calculation_execution"]["status"] == "ok"
    assert {
        slot["slot_id"]
        for slot in trace["authoritative_query_plan"]["evidence_slots"]
        if slot["role"] == "operand"
    } == {slot.slot_id for slot in bound.evidence_slots if slot.role == "operand"}


def test_finance_full_controller_chain_returns_verified_answer() -> None:
    evidence = _finance_ccc_evidence()
    request = DocQARequest(
        prompt=FINANCE_CCC_QUESTION,
        controller_question=FINANCE_CCC_QUESTION,
        retrieval_query=FINANCE_CCC_QUESTION,
        task_type="numeric",
        answer_type="numeric",
        verification_mode="light",
        verification_domain="finance",
        route_policy="doc",
        allowed_routes=["doc_text"],
        origin="benchmark",
    )

    def retrieve(_request, _decision):
        return {"evidence": evidence}

    def generate(_request, decision, bundle):
        return route_finance_numeric_answer(request, decision, bundle)

    execution = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=generate,
    )
    assert execution.answer == "-3.7"
    assert execution.retrieve_decision.status == "good"
    assert execution.verify_decision.status == "supported"
    assert execution.guardrail_decision.action == "return"
    assert (
        execution.evidence_bundle.metadata["finance_numeric_trace"]["attempt_status"]
        == "executed"
    )


def test_slidevqa_comparison_uses_visual_support_slot_for_page_image() -> None:
    question = "Regarding CCD customers, is a greater percentage MALE or FEMALE?"
    page = {
        "evidence_id": "page-image:slide-doc:6",
        "source_id": "slide-doc",
        "source_name": "slide-doc_page_6.jpg",
        "page_label": "6",
        "modality": "page_image",
        "evidence_level": "page",
        "source_backrefs": ["slide-doc#page:6"],
        "extension_metadata": {
            "visual_backend_type": "provided_image",
            "visual_retriever": "colqwen",
            "visual_retriever_score": 21.125,
        },
        "metadata": {"visual_retriever_score": 0.99},
    }
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="extractive",
        verification_domain="slidevqa",
        route_policy="visual",
        allowed_routes=["doc_page_image"],
    )

    bundle = build_evidence_bundle(
        "doc_page_image",
        request,
        {"page_image_index": [page]},
    )

    plan = bundle.metadata["bound_query_plan"]
    [slot] = plan["evidence_slots"]
    assert plan["answer_type"] == "boolean"
    assert slot["slot_id"] == "support:visual_primary"
    assert slot["role"] == "support"
    assert slot["statement_kind"] == "visual_support"
    assert slot["modality"] == "page_image"
    assert slot["required_for_execution"] is False
    assert slot["status"] == "filled"
    assert slot["evidence_ids"]
    assert bundle.metadata["missing_required_slot_count"] == 0


def test_slidevqa_visual_answer_publishes_verified_page_authority() -> None:
    question = "Regarding CCD customers, is a greater percentage MALE or FEMALE?"
    page = {
        "evidence_id": "page-image:slide-doc:6",
        "source_id": "slide-doc",
        "source_name": "slide-doc_page_6.jpg",
        "page_label": "6",
        "modality": "page_image",
        "evidence_level": "page",
        "source_backrefs": ["slide-doc#page:6"],
    }
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="extractive",
        answer_type="extractive",
        modality="page_image",
        verification_mode="light",
        verification_domain="slidevqa",
        route_policy="visual",
        allowed_routes=["doc_page_image"],
        origin="benchmark",
    )
    understanding = understand_query(
        question,
        task_type="extractive",
        modality="page_image",
    )
    assert understanding["modalities"] == ["page_image"]

    bundle = build_evidence_bundle(
        "doc_page_image",
        request,
        {"page_image_index": [page]},
    )
    pipeline = SimpleNamespace(
        vlm_generator=SimpleNamespace(
            name="test_visual_generator",
            generate=lambda _request, _bundle: "FEMALE",
        )
    )
    answer = route_visual_answer(
        pipeline,
        request,
        bundle,
        evidence_only_fallback=False,
    )
    assert answer == "FEMALE"
    authority = bundle.metadata["visual_answer_authority"]
    assert authority["contract_id"] == "visual_evidence_authority.v1"
    assert authority["evidence_ids"]

    decision = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        bundle,
        answer,
    )
    assert decision.status == "supported"
    assert decision.verified_citations == authority["evidence_ids"]
    verified_bundle = with_verification_evidence(bundle, decision, request)
    assert verified_bundle.metadata["verified_evidence"]
    assert verified_bundle.metadata["bound_query_plan"]["stage"] == "verified"
    [slot] = verified_bundle.metadata["bound_query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_support"


def test_slidevqa_full_controller_chain_returns_verified_answer() -> None:
    question = "Regarding CCD customers, is a greater percentage MALE or FEMALE?"
    page = {
        "evidence_id": "page-image:slide-doc:6",
        "source_id": "slide-doc",
        "source_name": "slide-doc_page_6.jpg",
        "page_label": "6",
        "modality": "page_image",
        "evidence_level": "page",
        "source_backrefs": ["slide-doc#page:6"],
    }
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="extractive",
        answer_type="extractive",
        modality="page_image",
        verification_mode="light",
        verification_domain="slidevqa",
        route_policy="visual",
        allowed_routes=["doc_page_image"],
        origin="benchmark",
    )
    pipeline = SimpleNamespace(
        vlm_generator=SimpleNamespace(
            name="test_visual_generator",
            generate=lambda _request, _bundle: "FEMALE",
        )
    )

    def retrieve(_request, _decision):
        return {"page_image_index": [page]}

    def generate(_request, _decision, bundle):
        return route_visual_answer(
            pipeline,
            request,
            bundle,
            evidence_only_fallback=False,
        )

    execution = execute_controller_turn(
        request,
        retrieve=retrieve,
        generate=generate,
    )
    assert execution.answer == "FEMALE"
    assert execution.retrieve_decision.status == "good"
    assert execution.verify_decision.status == "supported"
    assert execution.guardrail_decision.action == "return"
    assert execution.evidence_bundle.metadata["verified_evidence"]


def test_visual_generator_records_only_page_identities_sent_to_vlm(
    monkeypatch: Any,
) -> None:
    pages = [
        {
            "evidence_id": "page-image:slide-doc:6",
            "source_id": "slide-doc",
            "page_label": "6",
            "modality": "page_image",
            "evidence_level": "page",
            "image_ref": "data:image/png;base64,ZmFrZQ==",
        },
        {
            "evidence_id": "page-image:slide-doc:7",
            "source_id": "slide-doc",
            "page_label": "7",
            "modality": "page_image",
            "evidence_level": "page",
            "image_ref": "data:image/png;base64,ZmFrZQ==",
        },
    ]
    request = SimpleNamespace(prompt="Which group is larger?", origin="benchmark")
    bundle = EvidenceBundle(route="doc_page_image", items=pages, metadata={})
    captured = {}

    def create(**kwargs):
        captured["content"] = kwargs["messages"][0]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="FEMALE"))]
        )

    generator = QwenVLVisualGenerator(max_images=1, max_output_tokens=16)
    monkeypatch.setattr(
        generator,
        "_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )
    assert generator.generate(request, bundle) == "FEMALE"
    assert bundle.metadata["visual_generation_evidence_ids"] == [
        identity_of(pages[0]).key
    ]
    assert sum(part["type"] == "image_url" for part in captured["content"]) == 1


def _finance_ccc_evidence() -> list[dict[str, str]]:
    return [
        _finance_cell(metric, row, period, value, statement_kind)
        for metric, row, period, value, statement_kind in (
            ("inventory", "Inventories", "2018", "1642.2", "balance_sheet"),
            ("inventory", "Inventories", "2019", "1559.3", "balance_sheet"),
            (
                "accounts_receivable",
                "Receivables",
                "2018",
                "1684.2",
                "balance_sheet",
            ),
            (
                "accounts_receivable",
                "Receivables",
                "2019",
                "1679.7",
                "balance_sheet",
            ),
            (
                "accounts_payable",
                "Accounts payable",
                "2018",
                "2746.2",
                "balance_sheet",
            ),
            (
                "accounts_payable",
                "Accounts payable",
                "2019",
                "2854.1",
                "balance_sheet",
            ),
            (
                "cost_of_goods_sold",
                "Cost of sales",
                "2019",
                "11108.4",
                "income_statement",
            ),
            ("net_sales", "Net sales", "2019", "16865.2", "income_statement"),
        )
    ]


def _finance_cell(
    metric: str,
    row_label: str,
    period: str,
    value: str,
    statement_kind: str,
) -> dict[str, str]:
    cell_id = f"{metric}-{period}"
    return {
        "evidence_id": cell_id,
        "cell_id": cell_id,
        "source_id": "GENERALMILLS_2019_10K",
        "page_label": "55" if statement_kind == "balance_sheet" else "53",
        "evidence_level": "cell",
        "cell_role": "data",
        "modality": "table",
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "period_kind": "fiscal_year",
        "value": value,
        "unit": "USD",
        "scale": "million",
        "currency": "USD",
        "statement_kind": statement_kind,
        "financial_scope": "consolidated",
        "text": (
            f"General Mills consolidated {statement_kind} {row_label} "
            f"{period} {value} USD million"
        ),
    }
