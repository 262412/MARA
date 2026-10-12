"""Deterministic evidence at the real planning, execution and verification seam."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import ensure_request_query_plan, retrieval_budget
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer
from ktem.reasoning.mara_visual_answering import route_visual_answer
from ktem_tests.plan_policy_characterization import COLLECTION, UNSUPPORTED, lossless
from ktem_tests.test_docqa_boolean_stabilization_characterization import (
    INDEXING_QUESTION,
    PARALLEL_QUESTION,
    _item,
    _parallel_candidates,
)
from ktem_tests.test_docqa_finance_collection_cardinality import _revolving_span
from ktem_tests.test_docqa_query_planning import _finance_cell
from ktem_tests.test_docqa_targeted_route_regressions import (
    FINANCE_CCC_QUESTION,
    _finance_ccc_evidence,
)

SEAMS = (
    "formula",
    "collection_recovered",
    "collection_partial",
    "missing_scale",
    "unsupported",
    "explicit_pages",
    "visual",
    "text_boolean",
    "conflict",
)


def observe_in_fixed_process():
    # The existing verifier projects a set of verified IDs into metadata. Fix
    # its interpreter input instead of sorting or dropping any observed IDs.
    completed = subprocess.run(
        [sys.executable, "-m", "ktem_tests.plan_policy_seams"],
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
    return json.loads(completed.stdout)


def _terminal_without_elapsed_values(state):
    # Baseline repeat captures differ only at these measured durations. Retain
    # the timing keys and validate their type; every business field stays exact.
    state = copy.deepcopy(state)
    metadata = state.get("evidence_bundle", {}).get("metadata", {})
    timings = metadata.get("pipeline_stage_timings", {})
    for name, value in timings.items():
        assert isinstance(value, (int, float)) and value >= 0
        timings[name] = "elapsed seconds"
    materialization = metadata.get("materialization_trace", {})
    if "materialization_seconds" in materialization:
        assert isinstance(materialization["materialization_seconds"], (int, float))
        assert materialization["materialization_seconds"] >= 0
        materialization["materialization_seconds"] = "elapsed seconds"
    for container in (metadata, metadata.get("evidence_selection_trace", {})):
        cache = container.get("boolean_assessment_cache", {})
        if "time_spent_ms" in cache:
            assert isinstance(cache["time_spent_ms"], (int, float))
            assert cache["time_spent_ms"] >= 0
            cache["time_spent_ms"] = "elapsed milliseconds"
    return state


def _inputs(name):
    if name == "formula":
        return FINANCE_CCC_QUESTION, "numeric", "finance", _finance_ccc_evidence()
    if name.startswith("collection"):
        return COLLECTION, "numeric", "finance", []
    if name == "unsupported":
        return UNSUPPORTED, "numeric", "finance", []
    if name == "missing_scale":
        items = [
            _finance_cell(
                "cash", "Operating cash flow", "2018", "100", "cash_flow_statement"
            ),
            _finance_cell(
                "capex", "Capital expenditure", "2018", "20", "cash_flow_statement"
            ),
        ]
        for item in items:
            item.pop("scale", None)
            item["text"] = f"{item['row_label']} 2018 {item['value']}"
        return (
            "What was free cash flow in millions for 2018?",
            "numeric",
            "finance",
            items,
        )
    if name == "explicit_pages":
        items = [
            {
                **_finance_cell("left", "Revenue", "2021", "100", "income_statement"),
                "page_label": "8",
            },
            {
                **_finance_cell("right", "Revenue", "2022", "120", "income_statement"),
                "page_label": "12",
            },
        ]
        return (
            "What was the percentage change in revenue from 2021 to 2022 on pages 8 and 12?",
            "numeric",
            "finance",
            items,
        )
    if name == "visual":
        return (
            "Regarding CCD customers, is a greater percentage MALE or FEMALE?",
            "extractive",
            "slidevqa",
            [
                {
                    "evidence_id": "page-image:slide-doc:6",
                    "source_id": "slide-doc",
                    "source_name": "slide-doc_page_6.jpg",
                    "page_label": "6",
                    "modality": "page_image",
                    "evidence_level": "page",
                    "source_backrefs": ["slide-doc#page:6"],
                }
            ],
        )
    if name == "text_boolean":
        return (
            INDEXING_QUESTION,
            "boolean",
            "qasper",
            [
                _item(
                    "direct-abstract",
                    "We present an indexing-based method for the creation of a silver-standard answer-retrieval dataset using the entire Wikipedia.",
                    section_id="abstract",
                )
            ],
        )
    assert name == "conflict"
    return PARALLEL_QUESTION, "boolean", "qasper", _parallel_candidates()


def observe_seam(name):
    question, answer_type, domain, items = _inputs(name)
    visual = name == "visual"
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type=answer_type,
        answer_type=answer_type,
        verification_domain=domain,
        verification_mode="strict" if domain == "qasper" else "light",
        route_policy="visual" if visual else "doc",
        allowed_routes=["doc_page_image" if visual else "doc_text"],
        origin="benchmark",
        modality="page_image" if visual else "auto",
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
        if name.startswith("collection"):
            facility = (
                "five_year:2023-05-26"
                if name == "collection_recovered" and current.retrieval_round_id == 2
                else "364_day:2023-05-26"
            )
            evidence = [_revolving_span(str(current.retrieval_round_id), facility)]
        return {"page_image_index" if visual else "evidence": evidence}

    def generate(current, decision, bundle):
        calls.append({"stage": "generate", "route": decision.route})
        if visual:
            pipeline = SimpleNamespace(
                vlm_generator=SimpleNamespace(
                    name="fixed_visual_boundary",
                    generate=lambda *_args: "FEMALE",
                )
            )
            return route_visual_answer(
                pipeline, current, bundle, evidence_only_fallback=False
            )
        if domain == "qasper":
            return "yes"
        return (
            route_finance_numeric_answer(current, decision, bundle)
            or "No numeric result."
        )

    result = execute_controller_turn(request, retrieve=retrieve, generate=generate)
    return _execution_observation(request, result, calls)


def _execution_observation(request, result, calls):
    metadata = result.evidence_bundle.metadata
    numeric = metadata.get("finance_numeric_trace", {})
    return lossless(
        {
            "calls": calls,
            "planned": request.planned_query_plan.as_dict(),
            "final_plan": request.query_plan.as_dict(),
            "plan_id": request.query_plan_id,
            "state_version": request.query_plan_state_version,
            "bound": metadata.get("bound_query_plan"),
            "controller": result.controller_decision.as_dict(),
            "retrieval": result.retrieve_decision.as_dict(),
            "verification": result.verify_decision.as_dict(),
            "guardrail": result.guardrail_decision.as_dict(),
            "answer": result.answer,
            "terminal_answer": result.engine_terminal_answer,
            "terminal_state": _terminal_without_elapsed_values(
                result.engine_terminal_state
            ),
            "terminal_verification": result.engine_verify_decision,
            "terminal_guardrail": result.engine_terminal_guardrail_decision,
            "rounds": metadata.get("retrieval_rounds"),
            "recovery": metadata.get("calculation_recovery_trace"),
            "numeric": {
                key: numeric.get(key)
                for key in (
                    "attempt_status",
                    "answer",
                    "formula",
                    "inputs",
                    "calculation_execution",
                    "calculation_verification",
                    "authoritative_query_plan",
                )
            },
        }
    )


if __name__ == "__main__":
    print(json.dumps({name: observe_seam(name) for name in SEAMS}, ensure_ascii=False))
