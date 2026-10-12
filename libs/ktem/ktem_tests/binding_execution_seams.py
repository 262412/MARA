"""Additional fixed-evidence seams through the actual execution and verifier."""

import copy
import json
import os
import subprocess
import sys

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import ensure_request_query_plan, retrieval_budget
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer
from ktem_tests.binding_contract_inputs import (
    CROSS_PAGE_QUESTION,
    QASPER_QUESTION,
    SEGMENT_QUESTION,
    cross_page_items,
    relation_items,
    segment_page,
)
from ktem_tests.plan_policy_seams import _execution_observation
from ktem_tests.test_docqa_finance_02987_recovery import QUESTION as REVENUE_QUESTION
from ktem_tests.test_docqa_finance_02987_recovery import (
    _ppe_evidence,
    _scaled_revenue,
    _unscaled_revenue,
)

SEAMS = (
    "segment",
    "segment_ready",
    "qasper_relation",
    "boolean_cross_page",
    "boolean_cross_page_support",
    "revenue_recovered",
)


def observe_in_fixed_process():
    completed = subprocess.run(
        [sys.executable, "-m", "ktem_tests.binding_execution_seams"],
        env={
            **os.environ,
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": os.pathsep.join(sys.path),
        },
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    assert "Traceback" not in completed.stderr
    return json.loads(completed.stdout)


def _inputs(name):
    base = {
        "segment_ready": "segment",
        "boolean_cross_page_support": "boolean_cross_page",
    }.get(name, name)
    question, answer_type, domain, items = {
        "segment": (SEGMENT_QUESTION, "extractive", "finance", [segment_page()]),
        "qasper_relation": (QASPER_QUESTION, "extractive", "qasper", relation_items()),
        "boolean_cross_page": (
            CROSS_PAGE_QUESTION,
            "boolean",
            "qasper",
            cross_page_items(),
        ),
        "revenue_recovered": (
            REVENUE_QUESTION,
            "numeric",
            "finance",
            [_unscaled_revenue(), *_ppe_evidence()],
        ),
    }[base]
    if name == "segment_ready":
        items[0]["text"] = items[0]["text"].replace("Revenue by", "Net revenue by", 1)
    if name == "boolean_cross_page_support":
        items[0][
            "text"
        ] = "The authors released the code publicly with the paper for the final evaluated system. Page 2."
    return question, answer_type, domain, items


def observe_seam(name):
    question, answer_type, domain, items = _inputs(name)
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type=answer_type,
        answer_type=answer_type,
        verification_domain=domain,
        verification_mode="strict" if domain == "qasper" else "light",
        route_policy="doc",
        allowed_routes=["doc_text"],
        origin="benchmark",
    )
    calls = []

    def retrieve(current, decision):
        calls.append(
            {
                "stage": "retrieve",
                "round": current.retrieval_round_id,
                "slot": current.retrieval_slot_id,
                "query": current.retrieval_query,
                "route": decision.route,
                "budget": retrieval_budget(ensure_request_query_plan(current)),
            }
        )
        evidence = copy.deepcopy(items)
        if name == "revenue_recovered" and current.retrieval_round_id == 2:
            evidence.extend(_scaled_revenue("70", "operations-70"))
        return {"evidence": evidence}

    def generate(current, decision, bundle):
        calls.append({"stage": "generate", "route": decision.route})
        if domain == "finance":
            return (
                route_finance_numeric_answer(current, decision, bundle)
                or "No numeric result."
            )
        return "yes" if answer_type == "boolean" else "WikiQA"

    result = execute_controller_turn(request, retrieve=retrieve, generate=generate)
    return _execution_observation(request, result, calls)


if __name__ == "__main__":
    print(json.dumps({name: observe_seam(name) for name in SEAMS}, ensure_ascii=False))
