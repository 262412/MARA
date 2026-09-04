import json
from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.calculation_claim_verification import calculation_claim_result
from ktem.docqa.claim_aggregation import aggregate_answer_claims
from ktem.docqa.evidence import EvidenceBundle, _coerce_item
from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_record_identity import unique_evidence_records
from ktem.docqa.multimodal_index import element_records_from_index_documents
from ktem.docqa.offline_layout_index import offline_element_records_for_file
from ktem.docqa.query_planning import build_query_plan, score_evidence_for_slot
from ktem.docqa.verification import verify_claim, verify_decision


def test_offline_sidecar_preserves_atomic_cell_fields(tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF")
    sidecar = tmp_path / "report.pdf.mara-elements.json"
    sidecar.write_text(
        json.dumps(
            {
                "layout_elements": [
                    {
                        "page_label": "4",
                        "evidence_id": "table-parent",
                        "element_id": "income-statement",
                        "cell_id": "revenue-2023",
                        "evidence_level": "cell",
                        "table_id": "income-statement",
                        "row_index": 2,
                        "column_index": 3,
                        "row_label": "Revenue",
                        "column_label": "2023",
                        "period": "2023",
                        "period_kind": "fiscal_year",
                        "value": "120",
                        "unit": "currency",
                        "scale": "million",
                        "currency": "USD",
                        "statement_kind": "income_statement",
                        "financial_scope": "consolidated",
                        "continuation_id": "income-pages-4-5",
                        "retrieval_lineage": [{"retriever_name": "sidecar"}],
                        "representations": [{"modality": "ocr", "text": "Revenue 120"}],
                        "ocr_text": "Revenue 120",
                        "vlm_text": "A revenue cell",
                        "modality": "table",
                        "text": "Revenue 120",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    [record] = offline_element_records_for_file(
        file_id="report",
        file_name="report.pdf",
        file_path=source,
    )

    assert identity_of(record).key == "cell:report:revenue-2023"
    for field in (
        "cell_id",
        "evidence_level",
        "table_id",
        "row_index",
        "column_index",
        "row_label",
        "column_label",
        "period",
        "period_kind",
        "value",
        "unit",
        "scale",
        "currency",
        "statement_kind",
        "financial_scope",
        "continuation_id",
        "retrieval_lineage",
        "representations",
        "ocr_text",
        "vlm_text",
    ):
        assert record[field]


def test_persisted_element_index_dedupes_by_canonical_identity():
    shared = {
        "evidence_id": "table-parent",
        "source_id": "report",
        "file_id": "report",
        "file_name": "report.pdf",
        "page_label": "4",
        "element_id": "income-statement",
        "table_id": "income-statement",
        "evidence_level": "cell",
        "modality": "table",
        "text": "Revenue",
    }
    documents = [
        SimpleNamespace(
            metadata={
                "type": "mara_element_index",
                "element_index_record": {
                    **shared,
                    "cell_id": cell_id,
                    "period": period,
                    "value": value,
                },
            }
        )
        for cell_id, period, value in (
            ("revenue-2022", "2022", "100"),
            ("revenue-2023", "2023", "120"),
        )
    ]

    records = element_records_from_index_documents(documents)

    assert [record["cell_id"] for record in records] == [
        "revenue-2022",
        "revenue-2023",
    ]


def test_duplicate_identity_merges_lineage_representations_and_backrefs():
    records = unique_evidence_records(
        [
            {
                "source_id": "report",
                "cell_id": "revenue",
                "text": "Revenue 120",
                "source_backrefs": ["runtime#page:4"],
                "retrieval_lineage": [{"retriever_name": "dense"}],
                "representations": [{"modality": "ocr", "text": "Revenue 120"}],
            },
            {
                "source_id": "report",
                "cell_id": "revenue",
                "text": "Revenue 120",
                "source_backrefs": ["canonical#page:6"],
                "retrieval_lineage": [{"retriever_name": "sparse"}],
                "representations": [{"modality": "vlm", "text": "Revenue 120"}],
            },
        ]
    )

    assert len(records) == 1
    assert len(records[0]["retrieval_lineage"]) == 2
    assert {item["modality"] for item in records[0]["representations"]} >= {
        "ocr",
        "vlm",
    }
    assert records[0]["source_backrefs"] == [
        "runtime#page:4",
        "canonical#page:6",
    ]


def test_runtime_source_id_survives_bundle_and_benchmark_projection():
    from ktem.docqa.benchmark_evidence import benchmark_evidence_record
    from ktem.docqa.evidence import build_evidence_bundle

    request = DocQARequest(
        prompt="What was revenue?",
        route_policy="doc",
        selected_file_ids=["runtime-report"],
    )
    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "runtime_source_id": "runtime-report",
                    "page_label": "4",
                    "span_id": "revenue",
                    "text": "Revenue was 120.",
                }
            ]
        },
    )

    projected = benchmark_evidence_record(bundle.items[0]).as_dict()

    assert bundle.items[0]["source_id"] == "runtime-report"
    assert projected["runtime_source_id"] == "runtime-report"
    assert identity_of(projected) == identity_of(bundle.items[0])


def test_boolean_cross_page_slots_keep_explicit_page_locators():
    plan = build_query_plan(
        "Across pages 4 and 9, did both methods improve accuracy?",
        answer_type="boolean",
    )

    paired = [
        slot
        for slot in plan.evidence_slots
        if slot.slot_id in {"support:left_subject", "support:right_subject"}
    ]
    locators = [slot.locator for slot in paired]
    assert all(locator is not None for locator in locators)
    assert [locator.page_label for locator in locators if locator is not None] == [
        "4",
        "9",
    ]


def test_finance_slots_keep_explicit_page_locators():
    plan = build_query_plan(
        "Using current assets on page 4 and current liabilities on page 9, "
        "calculate the ratio.",
        answer_type="numeric",
        verification_domain="finance",
    )

    operands = [slot for slot in plan.evidence_slots if slot.role == "operand"]
    locators = [slot.locator for slot in operands[:2]]
    assert all(locator is not None for locator in locators)
    assert [locator.page_label for locator in locators if locator is not None] == [
        "4",
        "9",
    ]


def test_multi_period_slots_keep_explicit_page_locators():
    plan = build_query_plan(
        "Using pages 4 and 9, what was the percentage change in revenue "
        "between 2022 and 2023?",
        answer_type="numeric",
    )

    locators = [slot.locator for slot in plan.evidence_slots]
    assert all(locator is not None for locator in locators)
    assert [locator.page_label for locator in locators if locator is not None] == [
        "4",
        "9",
    ]


def test_page_locator_matches_dataset_page_and_page_aliases():
    from ktem.docqa.query_plan_schema import EvidenceLocator, EvidenceSlot

    slot = EvidenceSlot(
        slot_id="support:page",
        role="support",
        metric="reported result",
        locator=EvidenceLocator(page_label="14"),
    )
    item = {
        "source_id": "report",
        "page_label": "12",
        "dataset_page": "14",
        "page_aliases": ["12", "14"],
        "text": "The reported result.",
    }

    assert score_evidence_for_slot(slot, item) > 0


def test_source_locator_matches_source_aliases_and_backrefs():
    from ktem.docqa.query_plan_schema import EvidenceLocator, EvidenceSlot

    slot = EvidenceSlot(
        slot_id="support:source",
        role="support",
        metric="result",
        locator=EvidenceLocator(source_id="canonical-report", page_label="5"),
    )
    item = {
        "source_id": "runtime-report",
        "source_aliases": ["canonical-report"],
        "source_backrefs": ["canonical-report#page:5"],
        "page_label": "3",
        "page_aliases": ["3", "5"],
        "text": "The result.",
    }

    assert score_evidence_for_slot(slot, item) > 0


def test_figure_label_survives_evidence_coercion():
    item = _coerce_item(
        {
            "evidence_id": "figure",
            "source_id": "paper",
            "page_label": "4",
            "element_id": "visual-3",
            "figure_label": "3",
            "modality": "figure",
            "text": "Architecture.",
        }
    )

    assert item["figure_label"] == "3"


def _calculation_bundle() -> EvidenceBundle:
    operand = {
        "source_id": "report",
        "cell_id": "revenue-change",
        "text": "Revenue increased by 20 percent.",
    }
    return EvidenceBundle(
        route="hybrid",
        items=[operand],
        metadata={
            "finance_numeric_trace": {
                "calculation_plan": {"answer_unit": "percent"},
                "calculation_verification": {"valid": True},
                "calculation_execution": {
                    "status": "ok",
                    "value": "20",
                    "citation_ids": [identity_of(operand).key],
                },
            }
        },
    )


def test_compound_numeric_sentence_does_not_hide_false_direction():
    request = DocQARequest(
        prompt="What was the percentage change in revenue?",
        task_type="numeric",
        verification_domain="finance",
        verification_mode="strict",
    )

    decision = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        _calculation_bundle(),
        "The percentage change was 20%, and revenue decreased.",
    )

    assert decision.status != "supported"
    assert any(
        result["status"] in {"contradicted", "conflicting"}
        for result in decision.claim_results
        if "decreased" in result["claim"].lower()
    )


def test_unrelated_negated_evidence_is_not_a_claim_contradiction():
    claim = "The classification model uses labeled features."
    supporting = {
        "source_id": "paper",
        "span_id": "support",
        "text": "The classification model uses labeled features.",
    }
    unrelated = {
        "source_id": "paper",
        "span_id": "unrelated",
        "text": (
            "The appendix does not release implementation code for a separate "
            "model discussed in future work."
        ),
    }

    result = verify_claim(
        claim,
        [supporting, unrelated],
        claim_id="claim:1",
        prompt="What features does the classification model use?",
    )

    assert result.status == "supported"
    assert result.contradicting_evidence_ids == ()


def test_related_negation_outside_claim_scope_does_not_override_exact_support():
    claim = (
        "Labeled features are manually provided indicators of specific classes, "
        'such as words like "amazing" for the positive class.'
    )
    exact_support = {
        "source_id": "paper",
        "span_id": "support",
        "text": (
            "Labeled features are manually provided indicators of specific "
            "classes, such as words like amazing for the positive class."
        ),
    }
    related_context = {
        "source_id": "paper",
        "span_id": "context",
        "text": (
            "The method incorporates not only labeled features but also class "
            "distribution. We build classification models without instance "
            "annotation, but with labeled features."
        ),
    }

    result = verify_claim(
        claim,
        [exact_support, related_context],
        claim_id="claim:1",
        prompt="What background knowledge does the method leverage?",
    )

    assert result.status == "supported"
    assert result.contradicting_evidence_ids == ()


def test_calculation_dimension_is_checked_on_result_claim_only():
    result = calculation_claim_result(
        _calculation_bundle(),
        "The change was 20. Another margin was 5 percent.",
        ["The change was 20.", "Another margin was 5 percent."],
        domain="finance",
    )

    assert result is not None
    assert result.status == "contradicted"


def test_generic_claim_with_support_and_contradiction_is_conflicting():
    result = verify_claim(
        "Model A outperformed Model B.",
        [
            {
                "source_id": "paper",
                "span_id": "yes",
                "text": "Model A outperformed Model B.",
            },
            {
                "source_id": "paper",
                "span_id": "no",
                "text": "Model A did not outperform Model B.",
            },
        ],
        claim_id="claim:1",
    )

    assert result.status == "conflicting"
    assert result.supporting_evidence_ids
    assert result.contradicting_evidence_ids


def test_supported_core_with_unknown_extension_requests_claim_pruning():
    request = DocQARequest(
        prompt="What features does the classification model use?",
        verification_mode="strict",
    )
    decision = verify_decision(
        request,
        SimpleNamespace(status="good", retry=False),
        EvidenceBundle(
            route="doc",
            items=[
                {
                    "source_id": "paper",
                    "span_id": "support",
                    "text": "The classification model uses labeled features.",
                }
            ],
        ),
        (
            "The classification model uses labeled features. "
            "It also depends on an undocumented graph module."
        ),
    )

    assert decision.action == "revise"
    assert decision.unsupported_claims == [
        "It also depends on an undocumented graph module."
    ]


def test_legacy_identity_alias_lookup_rejects_ambiguous_key():
    left = {"source_id": "a:b", "cell_id": "c"}
    right = {"source_id": "a", "cell_id": "b:c"}
    legacy_key = identity_of(left).legacy_key

    lookup = unambiguous_evidence_alias_lookup([left, right])

    assert legacy_key not in lookup
    assert identity_of(left).key in lookup
    assert identity_of(right).key in lookup


def test_verified_evidence_preserves_claim_mapping():
    from ktem.docqa.verification import VerifyDecision, with_verification_evidence

    items = [
        {"source_id": "paper", "span_id": "a", "text": "Claim A."},
        {"source_id": "paper", "span_id": "b", "text": "Claim B."},
    ]
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="supported",
        claims=["Claim A.", "Claim B."],
        verified_citations=[identity_of(item).key for item in items],
        claim_results=[
            {
                "claim_id": f"claim:{index}",
                "claim": f"Claim {label}.",
                "status": "supported",
                "supporting_evidence_ids": [identity_of(item).key],
                "contradicting_evidence_ids": [],
            }
            for index, (label, item) in enumerate(zip(("A", "B"), items), start=1)
        ],
    )

    verified = with_verification_evidence(
        EvidenceBundle(route="doc", items=items),
        decision,
    )

    assert verified.metadata["verified_claim_support_by_claim"] == {
        "claim:1": [identity_of(items[0]).key],
        "claim:2": [identity_of(items[1]).key],
    }


def test_claim_aggregation_splits_contrasting_clauses():
    answer, trace = aggregate_answer_claims(
        "Revenue increased, while operating profit declined."
    )

    assert answer.splitlines() == ["Revenue increased", "operating profit declined."]
    assert trace["input_claim_count"] == 2


def test_claim_aggregation_dedupes_reported_value_paraphrase():
    answer, trace = aggregate_answer_claims(
        "Revenue amounted to $10 million. "
        "The company reported $10 million in revenue."
    )

    assert answer.count("$10 million") == 1
    assert trace["duplicate_claim_count"] == 1
