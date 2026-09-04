from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_support import text_contradicts_claim
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_verification import _verify_nonempty_answer
from ktem.docqa.pipeline_stage_timings import PipelineStageTimings
from ktem.docqa.verification import VerifyDecision
from ktem.reasoning.mara_generation_context import cache_generation_context


def test_runtime_preserves_pre_verification_and_pre_guardrail_answers():
    bundle = EvidenceBundle(
        route="text",
        items=[
            {
                "source_id": "paper",
                "span_id": "support",
                "text": "The classification model uses labeled features.",
            }
        ],
    )
    decision = VerifyDecision(
        mode="strict",
        status="not_enough_evidence",
        reason="unsupported extension",
        action="abstain",
    )

    final_answer, _decision, _guardrail, _trace = _verify_nonempty_answer(
        DocQARequest(prompt="What background knowledge is used?"),
        SimpleNamespace(),
        RetrieveDecision(status="good", reason="test evidence"),
        bundle,
        "Labeled features and an unsupported graph module.",
        None,
        [],
        PipelineStageTimings(),
        verify=lambda *_args: decision,
        guardrail_factory=lambda status, action, reason: SimpleNamespace(
            status=status,
            action=action,
            reason=reason,
        ),
        abstain_message="MARA could not retrieve enough evidence.",
    )

    assert final_answer.startswith("MARA could not")
    assert bundle.metadata["pre_verification_answer"] == (
        "Labeled features and an unsupported graph module."
    )
    assert bundle.metadata["pre_guardrail_answer"] == (
        "Labeled features and an unsupported graph module."
    )


def test_unrelated_negated_fragment_does_not_contradict_supported_claim():
    claim = "The model uses manually provided labeled features."
    evidence = (
        "The model uses manually provided labeled features for classification. "
        "Neutral features do not need manual annotation."
    )

    assert text_contradicts_claim(claim, evidence) is False


def test_selected_bundle_is_the_actual_cached_generation_context():
    original_docs = [
        SimpleNamespace(doc_id="noise", text="unrelated references", metadata={}),
    ]
    pipeline = SimpleNamespace(
        _mara_cached_retrieval=(
            "What background knowledge is used?",
            [],
            original_docs,
            [],
        )
    )
    bundle = EvidenceBundle(
        route="text",
        items=[
            {
                "source_id": "paper",
                "evidence_id": "support",
                "text": "The model uses manually provided labeled features.",
                "metadata": {"file_name": "paper.txt"},
            },
            {
                "source_id": "paper",
                "evidence_id": "context",
                "text": "The experiments evaluate the proposed model.",
                "metadata": {"file_name": "paper.txt"},
            },
        ],
    )

    cache_generation_context(
        pipeline,
        "What background knowledge is used?",
        [],
        bundle,
    )

    _message, _history, cached_docs, _info = pipeline._mara_cached_retrieval
    assert [doc.doc_id for doc in cached_docs] == [
        "evidence:paper:support",
        "evidence:paper:context",
    ]
    assert [doc.text for doc in cached_docs] == [
        "The model uses manually provided labeled features.",
        "The experiments evaluate the proposed model.",
    ]
