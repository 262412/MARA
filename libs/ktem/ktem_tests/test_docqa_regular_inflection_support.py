import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.verification import verify_decision

POLICY = (
    "The Harbor sensor pilot retains raw sensor logs for exactly 17 days. "
    "Delete raw sensor logs after 17 days. "
    "The policy applies to raw sensor logs collected by the Harbor pilot. "
    "Aggregated daily summaries are kept separately and are not covered by "
    "this raw-log retention period. The laboratory coordinator owns this policy."
)
CORE = "The Harbor sensor pilot retains raw sensor logs for exactly 17 days."
RECORDED_EXTENSION = (
    "The policy states that raw sensor logs must be deleted after 17 days "
    "it applies specifically to raw sensor logs collected by the Harbor pilot."
)


def verification(answer, text=POLICY):
    request = DocQARequest(
        prompt="For how many days does the Harbor sensor pilot retain raw sensor logs?",
        verification_mode="strict",
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "policy", "file_id": "policy", "text": text}],
    )
    return verify_decision(
        request,
        RetrieveDecision(status="good", reason="Source retrieved"),
        bundle,
        answer,
    )


def test_recorded_supported_extension_is_not_rejected():
    decision = verification(CORE + " " + RECORDED_EXTENSION)
    assert decision.status == "supported"
    assert not decision.unsupported_claims
    assert not decision.unknown_claims


@pytest.mark.parametrize(
    "answer",
    [
        CORE.replace("17", "27"),
        "The Harbor sensor pilot does not retain raw sensor logs for exactly 17 days.",
        CORE + " " + RECORDED_EXTENSION.replace("17", "27"),
        CORE
        + " "
        + RECORDED_EXTENSION.replace("must be deleted", "must not be deleted"),
    ],
)
def test_inflection_support_preserves_contradiction_rejection(answer):
    assert verification(answer).status != "supported"


def test_missing_duration_remains_unverified():
    assert (
        verification(CORE, "The operating guide does not state a duration.").status
        != "supported"
    )
