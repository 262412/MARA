from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_support import text_contradicts_claim
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_verification import _verify_nonempty_answer
from ktem.docqa.pipeline_stage_timings import PipelineStageTimings
from ktem.docqa.verification import VerifyDecision


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
