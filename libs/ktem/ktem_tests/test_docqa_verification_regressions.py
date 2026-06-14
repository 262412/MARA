from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_filtering import answer_claims, clean_answer_text
from ktem.docqa.controller import build_controller_outputs
from ktem.docqa.execution import execute_controller_turn


def test_light_verifier_checks_final_answer_after_think_block_only():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="light"),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        },
        answer=(
            "<think>Profit declined sharply.</think>\n\n"
            "Final answer: Revenue increased in 2026."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["claims"] == ["Revenue increased in 2026."]
    assert payload["guardrail_decision"]["action"] == "return"


def test_clean_answer_text_keeps_markdown_final_answer_after_untagged_thought():
    answer = (
        "Thought Okay, I should inspect irrelevant scratch work first. "
        "Profit declined sharply.\n\n"
        "**Final Answer**: Revenue increased in 2026."
    )

    assert clean_answer_text(answer) == "Revenue increased in 2026."
    assert answer_claims(answer) == ["Revenue increased in 2026."]


def test_clean_answer_text_drops_untagged_thought_without_final_answer():
    answer = (
        "Thought Okay, let's inspect the filings. "
        "I need to find cost of sales before answering."
    )

    assert clean_answer_text(answer) == ""
    assert answer_claims(answer) == []


def test_verifier_abstains_reasoning_only_generation_without_claim_explosion():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        }

    def generate(_request, _decision, _bundle):
        return clean_answer_text(
            "Thought Okay, let's inspect the filings. "
            "I need to find cost of sales before answering."
        )

    result = execute_controller_turn(
        DocQARequest(prompt="Question", route_policy="doc", verification_mode="light"),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.verify_decision.status == "not_enough_evidence"
    assert result.verify_decision.claims == []
    assert result.verify_decision.unsupported_claims == []
    assert result.guardrail_decision.action == "abstain"


def test_light_verifier_ignores_markdown_final_answer_thought_prefix():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="light"),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        },
        answer=(
            "Thought Okay, I should inspect irrelevant scratch work first. "
            "Profit declined sharply.\n\n"
            "**Final Answer**: Revenue increased in 2026."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["claims"] == ["Revenue increased in 2026."]
    assert payload["guardrail_decision"]["action"] == "return"


def test_clean_answer_text_preserves_final_answer_markdown_table_lines():
    answer = (
        "Thought draft.\n\n"
        "**Final Answer**:\n"
        "| Metric | Value |\n"
        "| --- | ---: |\n"
        "| Revenue | 42 |\n"
    )

    assert clean_answer_text(answer) == (
        "| Metric | Value |\n" "| --- | ---: |\n" "| Revenue | 42 |"
    )


def test_light_verifier_ignores_rendered_thought_details_without_final_marker():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="light"),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": "Revenue increased in 2026.",
                }
            ]
        },
        answer=(
            "<details><summary><span style='color:grey'>Thought</span></summary>"
            "<blockquote>Profit declined sharply.</blockquote></details>\n\n"
            "Revenue increased in 2026."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["claims"] == ["Revenue increased in 2026."]
    assert payload["guardrail_decision"]["action"] == "return"


def test_answer_claims_skip_markdown_table_and_keep_name_initials_together():
    answer = (
        "| Nominee | Votes Against |\n"
        "| --- | ---: |\n"
        "| Richard A. Johnson | 16,105,005 |\n"
        "| Dona D. Young | 6,074,467 |\n\n"
        "Richard A. Johnson received the highest number of votes against."
    )

    assert answer_claims(answer) == [
        "Richard A. Johnson received the highest number of votes against."
    ]


def test_verifier_rejects_unsupported_quick_ratio_numeric_result():
    payload = build_controller_outputs(
        DocQARequest(
            prompt=_quick_ratio_prompt(),
            verification_mode="strict",
        ),
        [],
        _quick_ratio_evidence_metadata(),
        answer=(
            "Based on current assets, inventories, and current liabilities, "
            "3M's quick ratio was 1.20."
        ),
    )

    assert payload["verify_decision"]["status"] == "unsupported"
    assert payload["verify_decision"]["unsupported_claims"] == [
        (
            "Based on current assets, inventories, and current liabilities, "
            "3M's quick ratio was 1.20."
        )
    ]
    assert payload["verify_decision"]["action"] == "revise"
    assert payload["guardrail_decision"]["action"] == "revise"


def test_verifier_supports_quick_ratio_result_matching_evidence_numbers():
    payload = build_controller_outputs(
        DocQARequest(
            prompt=_quick_ratio_prompt(),
            verification_mode="strict",
        ),
        [],
        _quick_ratio_evidence_metadata(),
        answer=(
            "Based on current assets, inventories, and current liabilities, "
            "3M's quick ratio was 0.96."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["guardrail_decision"]["action"] == "return"


def test_verifier_focuses_finance_questions_on_final_numeric_conclusion():
    payload = build_controller_outputs(
        DocQARequest(
            prompt=_quick_ratio_prompt(),
            verification_mode="light",
        ),
        [],
        _quick_ratio_evidence_metadata(),
        answer=(
            "<details><summary><span style='color:grey'>Thought</span></summary>"
            "<blockquote>Try unrelated liquidity commentary first.</blockquote>"
            "</details>\n\n"
            "Final answer: 3M's quick ratio was 0.96, which is below 1, so "
            "the quick-ratio view does not show a reasonably healthy liquidity "
            "profile. Cash reserves and capital-market access are contextual "
            "factors but not the final numeric conclusion."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["claims"] == [
        (
            "3M's quick ratio was 0.96, which is below 1, so the quick-ratio "
            "view does not show a reasonably healthy liquidity profile."
        )
    ]
    assert payload["guardrail_decision"]["action"] == "return"


def test_execute_controller_turn_abstains_on_unsupported_quick_ratio_result():
    def retrieve(_request, _decision):
        return _quick_ratio_evidence_metadata()

    def generate(_request, _decision, _bundle):
        return (
            "Based on current assets, inventories, and current liabilities, "
            "3M's quick ratio was 1.20."
        )

    result = execute_controller_turn(
        DocQARequest(
            prompt=_quick_ratio_prompt(),
            route_policy="doc",
            verification_mode="strict",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.verify_decision.status == "unsupported"
    assert result.guardrail_decision.action == "abstain"
    assert result.answer


def _quick_ratio_prompt() -> str:
    return (
        "Does 3M have a reasonably healthy liquidity profile based on its quick "
        "ratio for Q2 of FY2023?"
    )


def _quick_ratio_evidence_metadata() -> dict:
    return {
        "evidence": [
            {
                "evidence_id": "balance-sheet-page",
                "file_id": "file-1",
                "page_label": "4",
                "text": (
                    "Total current assets $15,754 million. "
                    "Total inventories $5,280 million. "
                    "Total current liabilities $10,936 million."
                ),
            }
        ]
    }
