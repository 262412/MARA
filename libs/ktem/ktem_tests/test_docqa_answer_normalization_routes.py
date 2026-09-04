import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_filtering import clean_answer_text
from ktem.docqa.execution import execute_controller_turn


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode"),
    (
        ("doc", ["doc_text"], None),
        ("auto", ["doc_text", "hybrid"], None),
        ("auto", ["doc_text", "hybrid"], "thorough"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_mixed_latex_answer_wrapper_is_normalized_before_authority(
    route_policy, allowed_routes, agent_mode
):
    answer = (
        "MRC neural networks general knowledge human beings\n"
        r"$$ \text{Answer: KAR is an end-to-end MRC model.} $$"
    )
    evidence = [
        {
            "evidence_id": "direct",
            "source_id": "paper",
            "section_id": "method",
            "text": (
                "As shown in Figure 7, KAR is an end-to-end MRC model "
                "consisting of five layers."
            ),
        }
    ]
    request = DocQARequest(
        prompt="What type of model is KAR?",
        retrieval_query="What type of model is KAR?",
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=allowed_routes,
        agent_mode=agent_mode,
        selected_file_ids=["paper"],
        origin="benchmark",
    )

    result = execute_controller_turn(
        request,
        retrieve=lambda *_args: {"evidence": evidence},
        generate=lambda *_args: answer,
    )

    assert clean_answer_text(answer) == "KAR is an end-to-end MRC model."
    assert result.answer == "KAR is an end-to-end MRC model."
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
