"""Fixed inputs for ordinary/monotonic R4-B binding and two-round contracts."""

from dataclasses import replace

from ktem.docqa.query_plan_schema import (
    EvidenceLocator,
    EvidenceSlot,
    QueryPlan,
    with_plan_id,
)
from ktem.docqa.query_planning import build_query_plan
from ktem_tests.plan_policy_characterization import COLLECTION
from ktem_tests.test_docqa_binding_candidate_contracts import item
from ktem_tests.test_docqa_cross_page_query_plan import _boolean_page
from ktem_tests.test_docqa_finance_02987_recovery import _plan as revenue_plan
from ktem_tests.test_docqa_finance_02987_recovery import (
    _ppe_evidence,
    _scaled_revenue,
    _unscaled_revenue,
)
from ktem_tests.test_docqa_finance_collection_cardinality import _revolving_span
from ktem_tests.test_docqa_selection_assessment_snapshot import QUESTION, _items

SEGMENT_QUESTION = (
    "From FY21 to FY22, excluding Embedded, in which AMD reporting "
    "segment did sales proportionally increase the most?"
)
CROSS_PAGE_QUESTION = "Across pages 1 and 2, did the authors release the code?"
QASPER_QUESTION = "What dataset do the authors evaluate their method on?"
CASES = (
    "empty",
    "generic_operands",
    "duplicate_identity",
    "same_local_other_source",
    "old_valid",
    "old_missing",
    "old_unresolved",
    "old_incompatible",
    "old_partial",
    "old_verified_support",
    "old_verified_conflict",
    "dimension_untrusted",
    "collection_recovered",
    "collection_still_partial",
    "collection_withdrawn",
    "revenue_provenance",
    "segment",
    "boolean",
    "boolean_cross_page",
    "qasper_relation",
    "no_identity",
    "explicit_locator",
    "visual",
)


def segment_page():
    return item(
        "segment-page",
        source_id="AMD_2022_10K",
        page_label="48",
        table_group_id="segment-revenue",
        modality="table",
        text=(
            "Revenue by reporting segment (in millions)\n2022 2021\n"
            "Data Center 6,043 3,694\nClient 6,201 6,887\n"
            "Gaming 6,805 5,607\nEmbedded 4,552 246"
        ),
    )


def cross_page_items():
    return [
        _boolean_page(
            "page-2",
            "2",
            "Contract Study - Correction\nThe authors did not release the code "
            "for the final evaluated system. This correction explicitly supersedes "
            "the earlier release statement.\nPage 2",
        ),
        _boolean_page(
            "page-1",
            "1",
            "Contract Study - Methods\nThe authors released the code publicly "
            "with the paper. The release statement applies to the final evaluated system.\nPage 1",
        ),
    ]


def relation_items():
    return [
        item(
            "related",
            text="Previous work evaluates a model on SQuAD.",
            section_id="related_work",
        ),
        item(
            "method",
            text="We evaluate our method on the WikiQA dataset.",
            section_id="experiments",
        ),
        item(
            "noise",
            text="The optimizer uses a small learning rate.",
            section_id="methods",
        ),
    ]


def make_plan(*slots, **constraints):
    return with_plan_id(
        QueryPlan(
            "extractive", "lookup", evidence_slots=slots, constraints=constraints
        ),
        "R4-B fixed binding contract",
    )


def _old_binding_case(name):
    status = {
        "old_missing": "missing",
        "old_partial": "retrieved_partial",
        "old_verified_support": "verified_support",
        "old_verified_conflict": "verified_conflict",
    }.get(name, "filled")
    slot = EvidenceSlot(
        "s",
        "support",
        metric="topic",
        status=status,
        evidence_ids=("evidence:paper:a",),
        cardinality=2 if name == "old_partial" else 1,
    )
    a = item("a", text="topic")
    b = item("b", text="topic in millions", scale="million")
    if name == "old_unresolved":
        slot = replace(slot, evidence_ids=("evidence:paper:withdrawn",))
    if name == "old_incompatible":
        slot = replace(slot, locator=EvidenceLocator(source_id="another"))
        b["source_id"] = "another"
    return make_plan(slot), [[a, b]]


def _collection_case(name):
    plan = build_query_plan(
        COLLECTION, answer_type="numeric", verification_domain="finance"
    )
    a = _revolving_span("one", "364_day:2023-05-26")
    b = _revolving_span("two", "five_year:2023-05-26")
    duplicate = _revolving_span("duplicate", "364_day:2023-05-26")
    rounds = {
        "collection_recovered": [[a], [a, duplicate, b]],
        "collection_still_partial": [[a], [a, duplicate]],
        "collection_withdrawn": [[a, b], [b]],
    }
    return plan, rounds[name]


def case_inputs(name):
    if name.startswith("old_"):
        return _old_binding_case(name)
    if name.startswith("collection_"):
        return _collection_case(name)
    if name == "revenue_provenance":
        initial = [_unscaled_revenue(), *_ppe_evidence()]
        return revenue_plan(), [
            initial,
            [*initial, *_scaled_revenue("70", "operations-70")],
        ]
    if name == "segment":
        return build_query_plan(
            SEGMENT_QUESTION, answer_type="extractive", verification_domain="finance"
        ), [[segment_page()]]
    if name in {"boolean", "boolean_cross_page", "qasper_relation"}:
        question, answer, items = {
            "boolean": (QUESTION, "boolean", _items()),
            "boolean_cross_page": (CROSS_PAGE_QUESTION, "boolean", cross_page_items()),
            "qasper_relation": (QASPER_QUESTION, "extractive", relation_items()),
        }[name]
        return build_query_plan(
            question, answer_type=answer, verification_domain="qasper"
        ), [items]
    return _simple_case(name)


def _simple_case(name):
    slot = EvidenceSlot("s", "support", metric="topic")
    if name == "empty":
        return make_plan(slot), [[]]
    if name == "no_identity":
        return make_plan(slot), [[{}]]
    if name == "generic_operands":
        return make_plan(
            EvidenceSlot("a", "operand", metric="topic", cardinality=3),
            EvidenceSlot("b", "operand", metric="topic"),
        ), [[item(x, text="topic", value="2", evidence_level="span") for x in "abcd"]]
    if name in {"duplicate_identity", "same_local_other_source"}:
        return make_plan(slot), [
            [
                item("a", text="topic"),
                item(
                    "a",
                    source_id="other" if name == "same_local_other_source" else "paper",
                    text="topic",
                    value="different fact",
                ),
            ]
        ]
    if name == "dimension_untrusted":
        header = item("header", text="Unrelated amounts", scale="million")
        dimension = EvidenceSlot(
            "d",
            "dimension",
            scale="million",
            status="filled",
            evidence_ids=("evidence:paper:header",),
        )
        return make_plan(dimension), [[header]]
    if name == "explicit_locator":
        return make_plan(
            replace(slot, locator=EvidenceLocator(source_id="paper", page_label="2"))
        ), [
            [
                item("a", text="topic", page_label="1"),
                item("b", text="topic", page_label="2"),
            ]
        ]
    assert name == "visual"
    visual = EvidenceSlot(
        "visual", "support", statement_kind="visual_support", modality="page_image"
    )
    return make_plan(visual), [
        [
            item("page", modality="page_image", evidence_level="page"),
            item("text", text="topic"),
        ]
    ]
