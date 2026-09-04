"""Build the QASPER quality-focused 6x3 diagnostic manifest.

The cases are deliberately selected from the 2026-09-02 full run.  The
answerable rows cover distinct failure boundaries, including a Boolean case
whose full-run trace performed targeted retrieval and added evidence.  The
unanswerable control is a question for which the source annotation has no
supporting evidence and the paper does not state the requested conclusion.
The manifest therefore tests the same three routes without reusing the
legacy six-row sample.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .manifest_subset import build_manifest_subset

QASPER_QUALITY_FOCUS_CONTRACT = "qasper_quality_focus_6x3.v2"
QASPER_QUALITY_FOCUS_ROUTES = (
    "text_rag",
    "controller_auto",
    "crag_guarded",
)
QASPER_QUALITY_FOCUS_SOURCE_RUN_SHA = "fab6a5a47a084407e665573588526173ebc6fe62"

_LEGACY_QASPER_FOCUS_IDS = frozenset(
    {
        "e330e162ec29722f5ec9f83853d129c9e0693d65",
        "6568a31241167f618ef5ede939053feaa2fb0d7e",
        "f2155dc4aeab86bf31a838c8ff388c85440fce6e",
        "7cd22ca9e107d2b13a7cc94252aaa9007976b338",
        "25c1c4a91f5dedd4e06d14121af3b5921db125e9",
        "e97186c51d4af490dba6faaf833d269c8256426c",
    }
)

QASPER_QUALITY_FOCUS_CASES: tuple[dict[str, Any], ...] = (
    {
        "example_id": "97d1ac71eed13d4f51f29aac0e1a554007907df8",
        "failure_class": "title_only_authority",
        "gold_class": "answerable",
        "diagnostic_target": "retrieved body evidence must become typed authority",
    },
    {
        "example_id": "0682bf049f96fa603d50f0fdad0b79a5c55f6c97",
        "failure_class": "canonical_pack_binding_mismatch",
        "gold_class": "answerable",
        "diagnostic_target": "canonical semantic pack must be transaction-consistent",
    },
    {
        "example_id": "3cd185b7adc835e1c4449eff81222f5fc15c8500",
        "failure_class": "claim_extension_overreach",
        "gold_class": "answerable",
        "diagnostic_target": "answer claims must stay inside supported evidence",
    },
    {
        "example_id": "d64383e39357bd4177b49c02eb48e12ba7ffd4fb",
        "failure_class": "question_predicate_unresolved",
        "gold_class": "answerable",
        "diagnostic_target": "question predicate must be resolved before abstention",
    },
    {
        "example_id": "1f085b9bb7bfd0d6c8cba1a9d73f08fcf2da7590",
        "failure_class": "retrieval_recovery_new_evidence",
        "gold_class": "answerable",
        "diagnostic_target": "targeted recovery must add evidence before re-verification",
        "recovery_expectation": {
            "stage": "targeted_retrieval",
            "action": "targeted_slot_retrieval",
            "minimum_new_evidence": 1,
            "observed_new_evidence": 2,
        },
    },
    {
        "example_id": "c34e80fbbfda0f1786d3b00e06cef5ada78a3f3c",
        "failure_class": "unanswerable_control",
        "gold_class": "unanswerable",
        "diagnostic_target": "negative control must have no direct source conclusion",
        "negative_control_basis": "empty_gold_evidence_and_no_source_conclusion",
    },
)


def build_qasper_quality_focus_manifest(
    source: Mapping[str, Any],
    *,
    source_run_sha: str = QASPER_QUALITY_FOCUS_SOURCE_RUN_SHA,
    source_artifact: str = "",
) -> dict[str, Any]:
    """Return the frozen, current-run-derived QASPER 6x3 manifest."""

    _validate_routes(source)
    cases = [dict(case) for case in QASPER_QUALITY_FOCUS_CASES]
    case_ids = [str(case["example_id"]) for case in cases]
    if set(case_ids) & _LEGACY_QASPER_FOCUS_IDS:
        raise ValueError("quality focus cases overlap the legacy six-row sample")
    subset = build_manifest_subset(source, case_ids)
    examples = []
    cases_by_id = {case["example_id"]: case for case in cases}
    for example in subset["examples"]:
        case = deepcopy(cases_by_id[str(example["example_id"])])
        if _gold_class(example) != case["gold_class"]:
            raise ValueError(
                f"quality focus gold class mismatch: {example['example_id']}"
            )
        _validate_case_contract(example, case)
        example["quality_focus"] = case
        examples.append(example)
    subset["dataset_name"] = "qasper_quality_focus_6x3"
    subset["examples"] = examples
    subset["metadata"] = {
        **dict(subset.get("metadata") or {}),
        "quality_focus": {
            "contract_id": QASPER_QUALITY_FOCUS_CONTRACT,
            "source_run_sha": str(source_run_sha),
            "source_artifact": str(source_artifact),
            "selection_basis": "current_full_run_failure_taxonomy",
            "legacy_sample_reused": False,
            "case_count": len(cases),
            "route_count": len(QASPER_QUALITY_FOCUS_ROUTES),
            "expected_prediction_count": len(cases) * len(QASPER_QUALITY_FOCUS_ROUTES),
            "routes": list(QASPER_QUALITY_FOCUS_ROUTES),
            "cases": cases,
        },
    }
    return subset


def _validate_routes(source: Mapping[str, Any]) -> None:
    routes = source.get("routes")
    route_ids = tuple(
        str(route.get("route_id") or "").strip()
        for route in routes or ()
        if isinstance(route, Mapping)
    )
    if route_ids != QASPER_QUALITY_FOCUS_ROUTES:
        raise ValueError(
            "quality focus requires routes in order: "
            + ", ".join(QASPER_QUALITY_FOCUS_ROUTES)
        )


def _validate_case_contract(
    example: Mapping[str, Any], case: Mapping[str, Any]
) -> None:
    failure_class = str(case.get("failure_class") or "")
    if failure_class == "retrieval_recovery_new_evidence":
        expectation = case.get("recovery_expectation")
        if not isinstance(expectation, Mapping):
            raise ValueError("recovery case must declare recovery_expectation")
        minimum_new_evidence = int(expectation.get("minimum_new_evidence") or 0)
        observed_new_evidence = int(expectation.get("observed_new_evidence") or 0)
        if minimum_new_evidence < 1 or observed_new_evidence < minimum_new_evidence:
            raise ValueError("recovery case must declare observed new evidence")
        if str(expectation.get("stage") or "") != "targeted_retrieval":
            raise ValueError("recovery case must target targeted_retrieval")
        if str(expectation.get("action") or "") != "targeted_slot_retrieval":
            raise ValueError("recovery case must target targeted_slot_retrieval")
    elif failure_class == "unanswerable_control":
        if example.get("gold_evidence") or example.get("evidence_sources"):
            raise ValueError(
                f"negative control unexpectedly has gold evidence: {example['example_id']}"
            )
        if case.get("negative_control_basis") != (
            "empty_gold_evidence_and_no_source_conclusion"
        ):
            raise ValueError("negative control must declare an evidence-first basis")


def _gold_class(example: Mapping[str, Any]) -> str:
    answers = example.get("gold_answers")
    if answers is None:
        answers = example.get("answers")
    metadata = example.get("metadata")
    annotations = (
        metadata.get("qasper_answer_annotations")
        if isinstance(metadata, Mapping)
        else None
    )
    if annotations:
        unanswerable_flags = [
            annotation.get("unanswerable") is True
            for annotation in annotations
            if isinstance(annotation, Mapping)
        ]
        if unanswerable_flags and all(unanswerable_flags):
            return "unanswerable"
    answers = [
        " ".join(str(answer or "").casefold().split()) for answer in answers or ()
    ]
    return (
        "unanswerable"
        if answers and all(answer == "unanswerable" for answer in answers)
        else "answerable"
    )
