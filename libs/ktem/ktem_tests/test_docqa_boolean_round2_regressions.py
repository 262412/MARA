from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_evidence_scope import boolean_retrieval_query
from ktem.docqa.boolean_proposition_evidence import boolean_proposition_evidence_score
from ktem.docqa.evidence_planning import select_planned_evidence
from ktem.docqa.query_planning import build_query_plan, missing_slot_requests
from ktem.docqa.retrieval_rounds import retrieve_with_rounds

QUALITY_CONTROL_QUESTION = (
    "Are the automatically constructed datasets subject to quality control?"
)
ARTIFACT_CONTROL = (
    "We find automatically constructing probes to be vulnerable to annotation "
    "artifacts, which we carefully control for."
)


def _item(
    evidence_id: str,
    text: str,
    *,
    section_title: str = "Results",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_title": section_title,
        "text": text,
    }


def test_missing_boolean_verification_slot_requests_expanded_second_round_query():
    plan = build_query_plan(
        QUALITY_CONTROL_QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )

    [slot] = plan.evidence_slots
    assert slot.required_for_verification
    assert slot.statement_kind == "boolean_proposition"
    assert not slot.required_for_execution

    requests = missing_slot_requests(plan)

    assert len(requests) == 1
    assert requests[0]["slot_id"] == "support:boolean_proposition"
    assert "validate" in requests[0]["query"]
    assert "quality" in requests[0]["query"]


def test_e971_first_round_artifact_candidate_triggers_round2_without_execution_slot():
    request = DocQARequest(
        prompt=QUALITY_CONTROL_QUESTION,
        controller_question=QUALITY_CONTROL_QUESTION,
        retrieval_query=QUALITY_CONTROL_QUESTION,
        task_type="boolean",
        verification_domain="qasper",
    )

    _selected, metadata = select_planned_evidence(
        request,
        [
            _item(
                "artifact-control",
                ARTIFACT_CONTROL,
                section_title="Dataset Probes and Construction",
            )
        ],
    )

    assert metadata["missing_required_slot_count"] == 1
    [second_round] = metadata["second_round_requests"]
    assert second_round["slot_id"] == "support:boolean_proposition"
    assert "validate" in second_round["query"]
    assert "quality" in second_round["query"]
    assert not request.query_plan.evidence_slots[0].required_for_execution


def test_boolean_relation_synonyms_improve_candidate_score_without_scope_leakage():
    assert (
        boolean_proposition_evidence_score(
            "Did the authors train the model?",
            _item("fine-tuning", "We fine-tune the model."),
        )
        > 0
    )
    assert (
        boolean_proposition_evidence_score(
            "Did the authors annotate the corpus?",
            _item("labels", "We construct labels for the corpus."),
        )
        > 0
    )
    assert (
        boolean_proposition_evidence_score(
            "Did the authors train the model?",
            _item("prior-work", "Previous work fine-tuned the model."),
        )
        == 0
    )


def test_e971_missing_artifact_slot_retrieves_decisive_validation_paragraph_on_round2():
    request = DocQARequest(
        prompt=QUALITY_CONTROL_QUESTION,
        controller_question=QUALITY_CONTROL_QUESTION,
        retrieval_query=QUALITY_CONTROL_QUESTION,
        task_type="boolean",
        verification_domain="qasper",
    )
    calls: list[tuple[int, str, str]] = []
    decisive = (
        "It is much harder to validate the quality of such data at such a scale "
        "and such varying levels of complexity."
    )

    def retrieve(current_request, _decision):
        calls.append(
            (
                current_request.retrieval_round_id,
                current_request.retrieval_query,
                current_request.retrieval_slot_id,
            )
        )
        if current_request.retrieval_round_id == 1:
            return {"evidence": [_item("artifact-control", ARTIFACT_CONTROL)]}
        return {
            "evidence": [
                _item(
                    "quality-validation",
                    decisive,
                    section_title="Dataset Probes and Construction",
                )
            ]
        }

    def evaluate(_route, metadata, *, attempted_retry, **_kwargs):
        if not attempted_retry:
            assert metadata["missing_required_slot_count"] == 1
            return SimpleNamespace(status="ambiguous", retry=True)
        assert metadata["missing_required_slot_count"] == 0
        return SimpleNamespace(status="good", retry=False)

    bundle, _decision = retrieve_with_rounds(
        request,
        SimpleNamespace(legacy_route="doc"),
        retrieve,
        evaluate=evaluate,
        retry_poor=False,
    )

    assert len(calls) == 2
    assert calls[0][0] == 1
    assert calls[1][0] == 2
    assert calls[1][2] == "support:boolean_proposition"
    assert "validate" in calls[1][1]
    assert "quality" in calls[1][1]
    assert any(decisive in item["text"] for item in bundle.items)
    assert bundle.metadata["retrieval_rounds"] == 2


def test_generic_boolean_second_round_queries_cover_evidence_stage_gap_families():
    cases = (
        (
            "Did the authors use pretrained models?",
            ("pretrain", "model", "fine-tune"),
        ),
        (
            "Did the authors release the code?",
            ("release", "publish", "repository", "source code"),
        ),
        (
            "Did the authors collect their own datasets?",
            ("collect", "gather", "compile", "corpus"),
        ),
        (
            "Did the authors use a crowdsourcing platform for annotations?",
            ("crowdsource", "human annotator", "label", "platform"),
        ),
    )
    for question, expected_terms in cases:
        query = boolean_retrieval_query(question, second_round=True)
        assert all(term in query for term in expected_terms)
