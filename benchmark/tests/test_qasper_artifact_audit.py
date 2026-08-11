from __future__ import annotations

import json
from pathlib import Path

from benchmark.qasper_artifact_audit import (
    audit_qasper_predictions,
    audit_qasper_predictions_file,
)


def _prediction(
    *,
    example_id: str,
    route: str,
    gold: str,
    product: str,
    contract: str,
    final: str,
    rewrite_type: str = "none",
    include_pre_snapshot: bool = True,
) -> dict:
    trace = {
        "product_answer": product,
        "pre_contract_answer": product,
        "post_contract_answer": contract,
        "final_post_contract_answer": contract,
        "rewrite_applied": product != contract,
        "rewrite_type": rewrite_type,
        "pre_contract_verification": {"answer": product},
        "post_contract_verification": {"answer": contract},
    }
    prediction = {
        "example_id": example_id,
        "route": route,
        "gold_answers": [gold],
        "answer_for_scoring": final,
        "predicted_answer": final,
        "terminal_answer_state": {"answer": final},
        "evidence_metadata": {
            "answerability_contract_trace": trace,
        },
        "product_metrics": {
            "false_abstention": float(
                gold != "unanswerable" and final == "unanswerable"
            )
        },
    }
    if include_pre_snapshot:
        prediction["pre_contract_verification"] = {"answer": product}
    return prediction


def _sample_rows() -> list[dict]:
    specs = [
        (
            "a",
            "text_rag",
            "yes",
            "yes",
            "unanswerable",
            "unanswerable",
            "polarity_to_unanswerable",
        ),
        (
            "b",
            "text_rag",
            "no",
            "no",
            "unanswerable",
            "unanswerable",
            "polarity_to_unanswerable",
        ),
        (
            "c",
            "text_rag",
            "yes",
            "unanswerable",
            "yes",
            "yes",
            "unanswerable_to_polarity",
        ),
        ("d", "text_rag", "no", "yes", "no", "no", "answer_rewrite"),
        (
            "e",
            "text_rag",
            "unanswerable",
            "unanswerable",
            "free text",
            "unanswerable",
            "none",
        ),
        (
            "a",
            "crag_guarded",
            "yes",
            "unanswerable",
            "unanswerable",
            "unanswerable",
            "none",
        ),
        ("b", "crag_guarded", "no", "no", "no", "no", "none"),
        (
            "c",
            "crag_guarded",
            "yes",
            "unanswerable",
            "yes",
            "yes",
            "unanswerable_to_polarity",
        ),
        (
            "e",
            "crag_guarded",
            "unanswerable",
            "unanswerable",
            "unanswerable",
            "unanswerable",
            "none",
        ),
    ]
    return [
        _prediction(
            example_id=example_id,
            route=route,
            gold=gold,
            product=product,
            contract=contract,
            final=final,
            rewrite_type=rewrite_type,
        )
        for example_id, route, gold, product, contract, final, rewrite_type in specs
    ]


def test_qasper_artifact_audit_reports_route_counts():
    audit = audit_qasper_predictions(_sample_rows())

    text = audit["routes"]["text_rag"]
    assert text["answerable_count"] == 4
    assert text["pre_contract_false_abstention_count"] == 1
    assert text["post_contract_false_abstention_count"] == 2
    assert text["final_false_abstention_count"] == 2
    assert text["correct_product_polarity_removed_count"] == 2
    assert text["correct_product_polarity_removed_by_value"] == {
        "yes": 1,
        "no": 1,
    }
    assert text["false_abstention_entering_contract_with_polarity_count"] == 2

    crag = audit["routes"]["crag_guarded"]
    assert crag["answerable_count"] == 3
    assert crag["pre_contract_false_abstention_count"] == 2
    assert crag["post_contract_false_abstention_count"] == 1
    assert crag["final_false_abstention_count"] == 1
    assert crag["correct_product_polarity_removed_count"] == 0
    assert crag["false_abstention_entering_contract_with_polarity_count"] == 0
    assert audit["totals"]["pre_contract_false_abstention_count"] == 3
    assert audit["totals"]["post_contract_false_abstention_count"] == 3
    assert audit["distinct_false_abstention_entering_contract_with_polarity_count"] == 2


def test_qasper_artifact_audit_reports_route_deltas_and_matrix():
    audit = audit_qasper_predictions(_sample_rows())

    assert audit["route_differences"] == {
        "engine_product_answer": 1,
        "post_contract_answer": 2,
        "final_answer": 1,
    }
    assert [
        (item["route"], item["engine"], item["contract"], item["final"], item["count"])
        for item in audit["transformation_matrix"]
    ] == [
        ("crag_guarded", "N", "N", "N", 1),
        ("crag_guarded", "U", "U", "U", 2),
        ("crag_guarded", "U", "Y", "Y", 1),
        ("text_rag", "N", "U", "U", 1),
        ("text_rag", "U", "F", "U", 1),
        ("text_rag", "U", "Y", "Y", 1),
        ("text_rag", "Y", "N", "N", 1),
        ("text_rag", "Y", "U", "U", 1),
    ]


def test_qasper_artifact_audit_uses_trace_when_top_level_pre_snapshot_is_missing():
    row = _prediction(
        example_id="missing-pre",
        route="text_rag",
        gold="unanswerable",
        product="unanswerable",
        contract="unanswerable",
        final="unanswerable",
        include_pre_snapshot=False,
    )

    audit = audit_qasper_predictions([row])

    assert audit["routes"]["text_rag"]["engine_product_answer_counts"]["U"] == 1
    assert audit["schema_gaps"] == {
        "answerability_trace_missing_count": 0,
        "engine_product_answer_missing_count": 0,
        "contract_post_answer_missing_count": 0,
        "top_level_pre_contract_verification_missing_count": 1,
        "trace_pre_contract_verification_missing_count": 0,
        "terminal_answer_state_missing_count": 0,
    }
    assert audit["field_paths"]["engine_product_answer"] == (
        "evidence_metadata.answerability_contract_trace.product_answer"
    )


def test_qasper_artifact_audit_file_loader_is_read_only(tmp_path: Path):
    path = tmp_path / "predictions.jsonl"
    row = _prediction(
        example_id="file-row",
        route="text_rag",
        gold="yes",
        product="unanswerable",
        contract="yes",
        final="yes",
        rewrite_type="unanswerable_to_polarity",
    )
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    before = path.read_bytes()
    audit = audit_qasper_predictions_file(path)

    assert audit["rows"] == 1
    assert audit["routes"]["text_rag"]["answerable_count"] == 1
    assert path.read_bytes() == before
