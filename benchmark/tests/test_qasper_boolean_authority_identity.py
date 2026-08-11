from __future__ import annotations

import json
from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.qasper_evidence_identity import canonical_prompt_span
from benchmark.qasper_quote_binding import _bind_authoritative_quote
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


class _Verifier:
    def __init__(self, verdict: str, quote: str) -> None:
        self.verdict = verdict
        self.quote = quote

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return type(
            "Result",
            (),
            {"text": f'{{"verdict":"{self.verdict}","evidence_quote":"{self.quote}"}}'},
        )()


def _item(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def _alias_mapping(items: list[dict[str, Any]]) -> str:
    aliases = []
    for index, item in enumerate(items, start=1):
        text = str(item["text"])
        aliases.append(
            {
                "evidence_ref": f"E{index}:S1",
                "runtime_evidence_id": identity_of(item).key,
                **canonical_prompt_span(
                    item,
                    text=text,
                    item_start=0,
                    item_end=len(text),
                ),
            }
        )
    return json.dumps(aliases)


def _artifact_experiment_evidence() -> dict[str, Any]:
    evidence = _item(
        "experiment",
        (
            "Sentence pairs are useful challenges for machine translation, but "
            "their construction is difficult to automate.\n\n"
            "## Current state of the art\n"
            "Machine translation systems provide broad coverage, although their "
            "handling of grammatical gender remains uneven across languages.\n\n"
            "For instance, the sentence is translated by Google Translate, Bing "
            "Translate, and Yandex. In fact, I have been unable to construct any "
            "English sentence that those systems translate using the feminine "
            "plural pronoun.\n\n"
            "The following discussion compares these observations with prior work."
        ),
    )
    evidence.update(
        {
            "canonical_start": 200,
            "canonical_end": 200 + len(evidence["text"]),
        }
    )
    evidence.pop("section_id")
    return evidence


def _apply_qasper_contract(prediction: dict[str, Any]) -> tuple[bool, bool]:
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    applied = apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: _Verifier("insufficient_evidence", ""),
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    return applied, synchronize_terminal_answer_state(prediction)


def test_grounded_complete_quote_without_unique_evidence_identity_is_rejected() -> None:
    quote = "We evaluated the model on clinical tasks."
    first = _item("first", quote)
    first.update({"canonical_start": 0, "canonical_end": len(quote)})
    second = _item("second", quote)
    second.update({"canonical_start": 100, "canonical_end": 100 + len(quote)})

    bound, status = _bind_authoritative_quote(
        "",
        quote,
        [first, second],
        alias_mapping=_alias_mapping([first, second]),
    )

    assert bound is None
    assert status == "quote_identity_unresolved"


def test_overlapping_chunks_with_the_same_canonical_quote_collapse_to_one_authority() -> None:
    quote = "We evaluated the model on clinical tasks."
    first = _item("first", quote)
    first.update({"canonical_start": 100, "canonical_end": 100 + len(quote)})
    second = _item("second", quote)
    second.update({"canonical_start": 100, "canonical_end": 100 + len(quote)})

    bound, status = _bind_authoritative_quote(
        "",
        quote,
        [first, second],
        alias_mapping=_alias_mapping([first, second]),
    )

    assert bound is not None
    assert status == "bound"
    assert bound.span.identity == (f"quote:paper:100:{100 + len(quote)}")


def test_deterministic_experiment_resolution_keeps_its_selected_evidence() -> None:
    quote = (
        "For instance, the sentence is translated by Google Translate, Bing "
        "Translate, and Yandex. In fact, I have been unable to construct any "
        "English sentence that those systems translate using the feminine "
        "plural pronoun."
    )
    evidence_item = _item("experiment", quote)
    evidence_item.update({"canonical_start": 200, "canonical_end": 200 + len(quote)})
    result = verify_qasper_answerability(
        _Verifier("insufficient_evidence", ""),
        question="Do the authors conduct experiments on the tasks mentioned?",
        evidence=quote,
        evidence_items=[evidence_item],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["verifier_input_evidence_ids"] == "evidence:paper:experiment"


def test_deterministic_experiment_support_survives_terminal_citation_rebuild() -> None:
    evidence = _artifact_experiment_evidence()
    plan = bind_evidence_slots(
        build_query_plan(
            "Do the authors conduct experiments on the tasks mentioned?",
            answer_type="boolean",
            verification_domain="qasper",
        ),
        [evidence],
    )
    [bound_slot] = plan.evidence_slots
    assert bound_slot.evidence_ids == (identity_of(evidence).key,)
    prediction: dict[str, Any] = {
        "question": "Do the authors conduct experiments on the tasks mentioned?",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "route": "hybrid",
        "gold_evidence": ["anonymous-support"],
        "evidence_bundle": {"items": [evidence], "metadata": {}},
        "evidence_metadata": {
            "selected_evidence": [evidence],
            "generation_context_evidence": [evidence],
            "query_plan": plan.as_dict(),
        },
        "structured_citations": [],
        "predicted_citations": [],
    }
    applied, synchronized = _apply_qasper_contract(prediction)

    assert applied is True
    assert synchronized is True
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["verify_decision"]["status"] == "supported"
    assert prediction["structured_citations"]
    assert prediction["evidence_metadata"]["verified_claim_support_evidence"] == [
        evidence
    ]
    assert prediction["predicted_evidence"] == [evidence["text"]]
    assert prediction["evidence_metadata"]["emitted_citation_evidence"] == [evidence]
    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=prediction["evidence_metadata"]["emitted_citation_evidence"],
        contract_items=[evidence],
    )
    assert metrics["citation_scope_violation_count"] == 0.0
    assert (
        contract_invariant_summary([prediction])["qasper_stale_verifier_state_count"]
        == 0.0
    )
    assert prediction["evidence_metadata"]["qasper_answerability"][
        "evidence_quote"
    ].startswith("In fact, I have been unable")
    answerability = prediction["evidence_metadata"]["qasper_answerability"]
    assert answerability["verifier_required_evidence_coverage"] == "1.000000"
    assert answerability["verifier_required_slot_authority_count"] == "1"
    assert answerability["authoritative_quote_evidence_id"] == identity_of(evidence).key
    assert (
        answerability["authoritative_quote_evidence_id"]
        in answerability["final_support_evidence_ids"]
    )
    assert answerability["evidence_quote"] in evidence["text"]
    emitted = prediction["evidence_metadata"]["emitted_citation_evidence"]
    assert [identity_of(item).key for item in emitted] == [identity_of(evidence).key]
    assert (
        prediction["structured_citations"][0]["evidence_id"]
        == identity_of(evidence).key
    )
