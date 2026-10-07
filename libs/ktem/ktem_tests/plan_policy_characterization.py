"""Fixed inputs and lossless observations for the R4-A baseline contract."""

from __future__ import annotations

import copy
import sys
from typing import Any

from ktem.docqa import query_planning as planning
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan

FIXED_ASSET = (
    "What is FY2019 fixed asset turnover using FY2019 revenue and "
    "average net PP&E for FY2018 and FY2019?"
)
UNSUPPORTED = "What was the revenue productivity turnover from FY2018 to FY2019?"
COLLECTION = (
    "As of May 26, 2023, what is the total amount PepsiCo may borrow under its "
    "unsecured revolving credit agreements?"
)
PAYLOAD: dict[str, Any] = {
    "answer_type": "numeric",
    "question_type": "planned",
    "plan_id": "plan:caller-supplied",
    "max_retrieval_rounds": 7,
    "subqueries": [" first ", "", "first", "second"],
    "constraints": {"verification_domain": "caller", "nested": {"value": [1]}},
    "evidence_slots": [
        {
            "slot_id": "caller:slot",
            "role": "operand",
            "query": " caller query ",
            "evidence_ids": [" x ", "", "x"],
            "locator": {"source_id": " source ", "page_labels": [" 8 ", "", "8", "12"]},
        }
    ],
}


def _case(name: str, question: Any, answer_type="", domain="", **kwargs) -> dict:
    return {
        "name": name,
        "arguments": {
            "question": question,
            "answer_type": answer_type,
            "verification_domain": domain,
            **kwargs,
        },
    }


CASES = [
    _case("empty", ""),
    _case("none_question", None),
    _case("unicode_text", "Who wrote α & β <notes>?", "free_text"),
    _case(
        "unknown_domain", "How many participants were included?", "numeric", "unknown"
    ),
    _case("numeric_finance", FIXED_ASSET, "numeric", "finance"),
    _case("finance_substring", FIXED_ASSET, "numeric", " preFINANCEpost "),
    _case("inferred_finance", FIXED_ASSET, "numeric"),
    _case("unsupported", UNSUPPORTED, "numeric", "finance"),
    _case("unsupported_unknown", UNSUPPORTED, "numeric", "unknown"),
    _case(
        "finance_not_applicable",
        "How many participants were included?",
        "numeric",
        "finance",
    ),
    _case(
        "scale_fcf",
        "What was free cash flow in millions for 2018?",
        "numeric",
        "finance",
    ),
    _case("fcf_no_scale", "What was FCF in 2018?", "numeric", "finance"),
    _case(
        "fact_support",
        "Identify the company's revenue for 2023.",
        "free_text",
        "finance",
    ),
    _case(
        "causal", "Why did revenue decline in 2021 and 2022?", "free_text", "finance"
    ),
    _case(
        "segment",
        "From FY21 to FY22, excluding Embedded, in which AMD reporting segment did sales proportionally increase the most?",
        "extractive",
        "finance",
    ),
    _case("collection_date", COLLECTION, "numeric", "finance"),
    _case(
        "collection_active",
        "What is the total revolving credit capacity?",
        "numeric",
        "finance",
    ),
    _case(
        "non_collection", "What is the revolving credit capacity?", "numeric", "finance"
    ),
    _case(
        "quarter_generic", "What was enrollment in Q1 FY2020 and Q2 FY2021?", "numeric"
    ),
    _case(
        "quarter_finance",
        "What was revenue in Q1 FY2020 and Q2 FY2021?",
        "numeric",
        "finance",
    ),
    _case(
        "visual_early",
        "How did revenue change from Q1 FY2020 to Q2 FY2021?",
        "free_text",
        "mmdoc_finance",
    ),
    _case(
        "slidevqa",
        "Regarding CCD customers, is a greater percentage MALE or FEMALE?",
        "extractive",
        " SlideVQA ",
    ),
    _case("slidevqa_nonexact", "Who wrote the paper?", "free_text", "prefix_slidevqa"),
    _case(
        "boolean",
        "Did the authors evaluate both clinical and legal datasets?",
        "boolean",
        "qasper",
    ),
    _case(
        "pages_equal",
        "What was the percentage change in revenue from 2021 to 2022 on pages 8 and 12?",
        "numeric",
        "finance",
    ),
    _case(
        "pages_unequal",
        "What was the percentage change in revenue from 2021 to 2022 on pages 8, 12 and 16?",
        "numeric",
        "finance",
    ),
    _case("focus_numeric", "What was gross margin in 2023?", "numeric", "finance"),
    _case(
        "focus_narrative",
        "Describe the primary customers and customer concentration.",
        "free_text",
        "finance",
    ),
    _case(
        "payload_empty_mapping", FIXED_ASSET, "numeric", "finance", planner_payload={}
    ),
    _case(
        "payload_empty_slots",
        "Describe the study.",
        planner_payload={"evidence_slots": []},
    ),
    _case(
        "payload_malformed_slots",
        "Describe the study.",
        planner_payload={"evidence_slots": "invalid"},
    ),
    _case(
        "payload_supported_override",
        FIXED_ASSET,
        "numeric",
        "finance",
        planner_payload=PAYLOAD,
    ),
    _case(
        "payload_unsupported_override",
        UNSUPPORTED,
        "numeric",
        "finance",
        planner_payload=PAYLOAD,
    ),
    _case(
        "payload_unknown_accept",
        FIXED_ASSET,
        "numeric",
        "unknown",
        planner_payload=PAYLOAD,
    ),
    _case(
        "payload_empty_domain_accept",
        FIXED_ASSET,
        "numeric",
        "",
        planner_payload=PAYLOAD,
    ),
    _case(
        "payload_nonnumeric_accept",
        FIXED_ASSET,
        "numeric",
        "finance",
        planner_payload={**PAYLOAD, "answer_type": "free_text"},
    ),
    _case(
        "payload_focus",
        "Describe primary customers.",
        "free_text",
        "finance",
        planner_payload={**PAYLOAD, "answer_type": "free_text"},
    ),
    _case(
        "payload_boolean",
        "Did the authors evaluate both clinical and legal datasets?",
        "boolean",
        "qasper",
        planner_payload={**PAYLOAD, "answer_type": "boolean"},
    ),
    _case(
        "payload_bad_rounds",
        FIXED_ASSET,
        "numeric",
        "finance",
        planner_payload={**PAYLOAD, "max_retrieval_rounds": "invalid"},
    ),
    _case(
        "payload_bad_constraints",
        FIXED_ASSET,
        "numeric",
        "finance",
        planner_payload={**PAYLOAD, "constraints": [1]},
    ),
    _case(
        "payload_bad_locator",
        FIXED_ASSET,
        "numeric",
        "finance",
        planner_payload={"evidence_slots": [{"locator": {"page_labels": 7}}]},
    ),
    _case("object_payload", "Describe the study.", planner_payload="original-object"),
]

# Observe unchanged helper implementations and retained compatibility entries.
# New strategy frames are deliberately outside this list; no result is filtered.
TRACE_FUNCTIONS = {
    "query_planning": {
        "_build_heuristic_query_plan",
        "_heuristic_evidence_slots",
        "_finance_slots",
        "_finance_retrieval_query",
        "_finance_dimension_query",
        "_finance_slot_locator",
        "_segment_comparison_slots",
        "_apply_fiscal_quarter_qualifiers",
        "_add_finance_formula_constraint",
        "_add_distinct_slot_constraint",
    },
    "query_plan_schema": {
        "initial_plan_from_payload",
        "plan_from_payload",
        "with_plan_id",
    },
    "query_phrase_extraction": {"periods_in_question", "metric_phrase"},
    "query_planning_lexicon": {"planning_tokens"},
    "query_classification": {
        "has_causal_intent",
        "normalized_answer_type",
        "question_capabilities",
        "question_type",
    },
    "query_evidence_constraints": {"period_kind_in_question"},
    "heuristic_query_slots": {"heuristic_slots", "mmdoc_visual_time_series_slots"},
    "finance_query_planning": {
        "finance_formula_status",
        "finance_formula_spec",
        "finance_operand_specs",
        "finance_fact_specs",
        "is_finance_segment_comparison",
    },
    "finance_retrieval_focus": {
        "apply_finance_retrieval_focus",
        "apply_finance_retrieval_focus_to_slots",
        "finance_comparison_operands_required",
        "finance_retrieval_focus_terms",
        "with_finance_retrieval_focus",
    },
    "query_plan_constraints": {"query_plan_constraints"},
    "boolean_conjunction": {"with_boolean_support_group"},
}


def lossless(value: Any) -> Any:
    """Keep tuple/list distinctions without dropping IDs or reordering results."""
    if isinstance(value, tuple):
        return {"__tuple__": [lossless(item) for item in value]}
    if isinstance(value, list):
        return [lossless(item) for item in value]
    if isinstance(value, dict):
        return {key: lossless(item) for key, item in value.items()}
    return value


def observe(case: dict) -> dict:
    arguments = copy.deepcopy(case["arguments"])
    if arguments.get("planner_payload") == "original-object":
        arguments["planner_payload"] = QueryPlan(
            "free_text",
            "planned",
            plan_id="plan:original-object",
            evidence_slots=(EvidenceSlot("caller", "support", query="study"),),
            constraints={"nested": {"value": [1]}},
        )
    before = copy.deepcopy(arguments)
    calls = []

    def profile(frame, event, _arg):
        module = frame.f_globals.get("__name__", "").rsplit(".", 1)[-1]
        name = frame.f_code.co_name
        if event == "call" and name in TRACE_FUNCTIONS.get(module, ()):
            calls.append(f"{module}.{name}")

    previous = sys.getprofile()
    sys.setprofile(profile)
    result: dict[str, Any]
    try:
        plan = planning.build_query_plan(**arguments)
    except (TypeError, ValueError) as error:
        result = {"exception": {"type": type(error).__name__, "message": str(error)}}
    else:
        result = {
            "plan": lossless(plan.as_dict()),
            "original_object": plan is arguments.get("planner_payload"),
            "budget": planning.retrieval_budget(plan),
            "round_two": planning.missing_slot_requests(plan),
            "coverage": planning.slot_coverage(plan),
        }
    finally:
        sys.setprofile(previous)
    assert arguments == before, "planning mutated caller input"
    return {**result, "calls": calls}
