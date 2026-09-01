from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from benchmark.docqa_response_projection import response_evidence_outputs
from benchmark.qasper_boolean_prompt import fit_boolean_verifier_prompt
from benchmark.qasper_evidence import qasper_paragraph_f1
from benchmark.qasper_evidence_identity import stabilize_qasper_evidence_projection
from benchmark.qasper_fresh_run_diff import compare_prediction_runs
from benchmark.qasper_prompt_budget import fit_qasper_verifier_items

FIXTURE_DIR = Path(__file__).with_name("fixtures")
TOOLKIT_REGRESSION_EXAMPLE = "5f2bade0881c719ab026bc2e2962e2ada96cdb25"


def _evidence(runtime_id: str, text: str, *, text_hash: str) -> dict[str, object]:
    return {
        "evidence_id": runtime_id,
        "source_id": f"runtime-source-{runtime_id}",
        "runtime_source_id": f"runtime-source-{runtime_id}",
        "evaluation_source_id": "paper-1",
        "document_id": "paper-1",
        "normalized_text_hash": text_hash,
        "section_id": "results",
        "text": text,
    }


def _fit(items: list[dict[str, object]]) -> tuple[str, str, dict[str, str]]:
    return fit_qasper_verifier_items(
        items,
        lambda evidence: f"QUESTION\n{evidence}",
        question="Did the authors evaluate the model on clinical tasks?",
        candidate_answer="unanswerable",
    )


def test_verifier_prompt_and_fingerprint_ignore_runtime_uuid_and_input_order() -> None:
    first = _evidence(
        "runtime-a",
        "We evaluated the model on clinical tasks.",
        text_hash="hash-a",
    )
    second = _evidence(
        "runtime-b",
        "The appendix describes implementation details.",
        text_hash="hash-b",
    )
    swapped_first = {**first, "evidence_id": "fresh-a", "source_id": "fresh-source-a"}
    swapped_second = {
        **second,
        "evidence_id": "fresh-b",
        "source_id": "fresh-source-b",
    }

    prompt_a, bounded_a, trace_a = _fit([first, second])
    prompt_b, bounded_b, trace_b = _fit([swapped_second, swapped_first])

    assert prompt_a == prompt_b
    assert bounded_a == bounded_b
    assert "runtime-a" not in prompt_a
    assert "runtime-b" not in prompt_a
    assert "fresh-a" not in prompt_b
    assert (
        trace_a["canonical_prompt_fingerprint"]
        == trace_b["canonical_prompt_fingerprint"]
    )
    assert "[evidence_ref=E1:S1]" in bounded_a
    aliases_a = json.loads(trace_a["verifier_evidence_alias_mapping"])
    aliases_b = json.loads(trace_b["verifier_evidence_alias_mapping"])
    assert [entry["evidence_ref"] for entry in aliases_a] == [
        entry["evidence_ref"] for entry in aliases_b
    ]
    assert aliases_a[0]["runtime_evidence_id"] != aliases_b[0]["runtime_evidence_id"]


def test_boolean_verifier_prompt_and_fingerprint_ignore_generator_candidate() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    evidence_items = [
        _evidence(
            "runtime-support",
            "We evaluated the model on clinical tasks.",
            text_hash="support-hash",
        ),
        _evidence(
            "runtime-contradiction",
            "We did not evaluate the model on legal tasks.",
            text_hash="contradiction-hash",
        ),
        _evidence(
            "runtime-candidate-overlap",
            "The appendix discusses a biomedical encoder and optimizer settings.",
            text_hash="candidate-overlap-hash",
        ),
    ]

    outputs = []
    for candidate in (
        "yes",
        "no",
        "The biomedical encoder was evaluated on clinical tasks.",
        "unanswerable",
    ):
        outputs.append(
            fit_boolean_verifier_prompt(
                question=question,
                evidence="\n".join(str(item["text"]) for item in evidence_items),
                evidence_items=evidence_items,
                candidate_answer=candidate,
                required_evidence_ids=None,
                required_slot_ids=None,
                priority_evidence_ids=None,
                claim_support_evidence_ids=None,
                claim_contradiction_evidence_ids=None,
            )
        )

    prompts = {prompt for prompt, _bounded, _trace in outputs}
    bounded_inputs = {bounded for _prompt, bounded, _trace in outputs}
    fingerprints = {
        trace["canonical_prompt_fingerprint"] for _prompt, _bounded, trace in outputs
    }
    alias_mappings = {
        trace["verifier_evidence_alias_mapping"] for _prompt, _bounded, trace in outputs
    }

    assert len(prompts) == 1
    assert len(bounded_inputs) == 1
    assert len(fingerprints) == 1
    assert len(alias_mappings) == 1


def test_qasper_projection_order_uses_canonical_provenance_not_runtime_ids() -> None:
    first = _evidence(
        "runtime-a",
        "First canonical span.",
        text_hash="hash-a",
    )
    first.update({"canonical_start": 10, "canonical_end": 31})
    second = _evidence(
        "runtime-b",
        "Second canonical span.",
        text_hash="hash-b",
    )
    second.update({"canonical_start": 40, "canonical_end": 62})
    fresh_first = {**first, "evidence_id": "fresh-z", "source_id": "fresh-z"}
    fresh_second = {**second, "evidence_id": "fresh-a", "source_id": "fresh-a"}

    metadata_a, hits_a = stabilize_qasper_evidence_projection(
        {"selected_evidence": [second, first]},
        [second, first],
    )
    metadata_b, hits_b = stabilize_qasper_evidence_projection(
        {"selected_evidence": [fresh_first, fresh_second]},
        [fresh_first, fresh_second],
    )

    assert (
        [item["text"] for item in hits_a]
        == [item["text"] for item in hits_b]
        == ["First canonical span.", "Second canonical span."]
    )
    assert [item["text"] for item in metadata_a["selected_evidence"]] == [
        item["text"] for item in metadata_b["selected_evidence"]
    ]


def test_docqa_response_projection_applies_qasper_canonical_order() -> None:
    first = _evidence(
        "runtime-a",
        "First canonical span.",
        text_hash="hash-a",
    )
    first.update({"canonical_start": 10, "canonical_end": 31})
    second = _evidence(
        "runtime-b",
        "Second canonical span.",
        text_hash="hash-b",
    )
    second.update({"canonical_start": 40, "canonical_end": 62})
    query_plan = {"constraints": {"verification_domain": "qasper"}}
    response = SimpleNamespace(
        answer="",
        references_text="",
        evidence_bundle={
            "items": [second, first],
            "metadata": {"query_plan": query_plan},
        },
        evidence_metadata={
            "selected_evidence": [second, first],
            "query_plan": query_plan,
        },
    )

    metadata, hits, *_outputs = response_evidence_outputs(
        response=response,
        documents=[],
        selected_file_ids=[],
    )

    expected = ["First canonical span.", "Second canonical span."]
    assert [item["text"] for item in hits] == expected
    assert [item["text"] for item in metadata["selected_evidence"]] == expected
    assert [item["text"] for item in response.evidence_bundle["items"]] == expected


def test_boolean_prompt_renders_one_continuous_proposition_window() -> None:
    text = (
        "We evaluate the model on clinical tasks. "
        + ("Unrelated background material. " * 90)
        + "We did not evaluate the model on legal tasks."
    )

    _prompt, bounded, trace = _fit([_evidence("runtime-a", text, text_hash="hash")])

    assert " … " not in bounded
    assert "[evidence_ref=E1:S1]" in bounded
    assert "[evidence_ref=E1:S2]" not in bounded
    assert bounded.endswith("We evaluate the model on clinical tasks.")
    spans = json.loads(trace["verifier_input_evidence_spans"])
    assert [entry["evidence_ref"] for entry in spans] == ["E1:S1"]
    assert all(entry["span_start"] < entry["span_end"] for entry in spans)


def test_qasper_evidence_f1_uses_maximum_cardinality_matching() -> None:
    predicted = ["alpha beta", "alpha x y z"]
    gold = ["alpha", "alpha beta"]

    assert qasper_paragraph_f1(predicted, gold) == 1.0
    assert qasper_paragraph_f1(list(reversed(predicted)), list(reversed(gold))) == 1.0


def test_qasper_evidence_f1_is_identical_across_python_hash_seeds() -> None:
    source = (
        "from benchmark.qasper_evidence import qasper_paragraph_f1; "
        "print(qasper_paragraph_f1(['alpha beta','alpha x y z'],"
        "['alpha','alpha beta']))"
    )
    repo_root = Path(__file__).resolve().parents[2]
    scores = []
    for seed in ("1", "2", "3", "4", "10"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", source],
            cwd=repo_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        scores.append(result.stdout.strip())

    assert scores == ["1.0"] * 5


def test_fresh_run_diff_ignores_runtime_ids_but_reports_semantic_drift() -> None:
    baseline: dict[str, Any] = {
        "example_id": "example-1",
        "route": "text_rag",
        "predicted_answer": "yes",
        "status": "ok",
        "retrieved_hits": [
            _evidence("runtime-a", "Stable evidence.", text_hash="stable-hash")
        ],
        "evidence_metadata": {
            "qasper_answerability": {
                "canonical_prompt_fingerprint": "prompt-a",
                "raw_verifier_verdict": "yes_complete",
                "evidence_quote": "Stable evidence.",
                "reason": "grounded_complete_proposition",
                "authoritative_quote_span_id": "quote:paper-1:0:16",
            }
        },
    }
    uuid_only = deepcopy(baseline)
    uuid_only["retrieved_hits"][0]["evidence_id"] = "fresh-a"
    semantic = deepcopy(uuid_only)
    semantic["predicted_answer"] = "no"
    candidate_only = deepcopy(uuid_only)
    candidate_only["evidence_metadata"][
        "pre_verification_answer"
    ] = "A different generator candidate."
    authority_only = deepcopy(uuid_only)
    authority_only["evidence_metadata"]["qasper_answerability"].update(
        {
            "adjudicated_polarity": "no",
            "authoritative_quote_evidence_id": "fresh-a",
            "authoritative_claim_key": [
                "current_paper",
                "evaluate",
                "dataset",
                "",
                "",
            ],
        }
    )

    ignored = compare_prediction_runs([baseline], [uuid_only])
    drifted = compare_prediction_runs([baseline], [semantic])
    candidate_drifted = compare_prediction_runs([baseline], [candidate_only])
    authority_drifted = compare_prediction_runs([baseline], [authority_only])

    assert ignored["aligned_prediction_count"] == 1
    assert ignored["runtime_only_identity_drift_count"] == 1
    assert ignored["canonical_retrieved_evidence_set_drift_count"] == 0
    assert ignored["unexpected_terminal_state_drift_count"] == 0
    assert drifted["unexpected_terminal_state_drift_count"] == 1
    assert candidate_drifted["candidate_state_drift_count"] == 1
    assert candidate_drifted["canonical_prompt_fingerprint_drift_count"] == 0
    assert candidate_drifted["unexpected_terminal_state_drift_count"] == 0
    assert authority_drifted["authority_drift_count"] == 1
    assert authority_drifted["unexpected_terminal_state_drift_count"] == 0


def test_qasper_toolkit_acceptance_target_has_verified_anchor_baseline() -> None:
    acceptance = json.loads(
        (FIXTURE_DIR / "qasper_fresh_run_acceptance.json").read_text(encoding="utf-8")
    )
    target_keys = {
        (entry["example_id"], entry["route"])
        for entry in acceptance["changes"]
        if entry["example_id"] == TOOLKIT_REGRESSION_EXAMPLE
        and entry["category"] == "target"
    }
    assert target_keys == {
        (TOOLKIT_REGRESSION_EXAMPLE, "text_rag"),
        (TOOLKIT_REGRESSION_EXAMPLE, "controller_auto"),
        (TOOLKIT_REGRESSION_EXAMPLE, "crag_guarded"),
    }
    baseline = {}
    with (FIXTURE_DIR / "qasper_golden_replay_v1.jsonl").open(
        encoding="utf-8"
    ) as stream:
        for line in stream:
            row = json.loads(line)
            key = (row.get("example_id"), row.get("route"))
            if key in target_keys and row.get("run_label") == "anchor_0343ba1":
                baseline[key] = row

    assert set(baseline) == target_keys
    for row in baseline.values():
        assert row["answer_status"] == "answered"
        assert row["terminal_outcome"] == "answered"
        assert row["typed_authority"]["state"] == "verified_support"
        assert row["verifier_decision"]["boolean_authority_status"] == (
            "verified_support"
        )


def test_fresh_run_diff_rejects_verified_support_regression() -> None:
    baseline = {
        "example_id": TOOLKIT_REGRESSION_EXAMPLE,
        "route": "text_rag",
        "answer_status": "answered",
        "terminal_outcome": "answered",
        "answer_for_scoring": "yes",
        "terminal_answer_state": {"answer": "yes", "status": "answered"},
        "typed_authority": {"state": "verified_support"},
    }
    candidate = {
        **baseline,
        "answer_status": "abstained",
        "terminal_outcome": "safe_abstention",
        "answer_for_scoring": "unanswerable",
        "terminal_answer_state": {
            "answer": "unanswerable",
            "status": "safe_abstention",
        },
        "typed_authority": {"state": "missing"},
    }

    diff = compare_prediction_runs(
        [baseline],
        [candidate],
        acceptance={
            "changes": [
                {
                    "example_id": TOOLKIT_REGRESSION_EXAMPLE,
                    "route": "text_rag",
                    "category": "target",
                    "allow_terminal_drift": True,
                }
            ]
        },
    )

    assert diff["verified_support_regression_count"] == 1
    [row] = diff["rows"]
    assert row["verified_support_regression"] is True
    assert row["unexpected_terminal_state_drift"] is True
    assert diff["unexpected_terminal_state_drift_count"] == 1


def test_fresh_run_diff_rejects_authority_loss_without_answer_drift() -> None:
    baseline = {
        "example_id": TOOLKIT_REGRESSION_EXAMPLE,
        "route": "text_rag",
        "answer_status": "answered",
        "terminal_outcome": "answered",
        "answer_for_scoring": "yes",
        "typed_authority": {"state": "verified_support"},
    }
    candidate = {**baseline, "typed_authority": {"state": "missing"}}

    diff = compare_prediction_runs(
        [baseline],
        [candidate],
        acceptance={
            "changes": [
                {
                    "example_id": TOOLKIT_REGRESSION_EXAMPLE,
                    "route": "text_rag",
                    "category": "target",
                    "allow_terminal_drift": True,
                }
            ]
        },
    )

    assert diff["verified_support_regression_count"] == 1
    assert diff["unexpected_terminal_state_drift_count"] == 1
