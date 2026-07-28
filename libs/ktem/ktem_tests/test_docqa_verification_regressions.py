from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_filtering import answer_claims, clean_answer_text
from ktem.docqa.controller import build_controller_outputs
from ktem.docqa.domain_verifiers import DomainVerifierRegistry
from ktem.docqa.evidence_text import extract_final_answer_text
from ktem.docqa.execution import execute_controller_turn
from ktem_tests.finance_test_fixtures import (
    quick_ratio_evidence_metadata as _quick_ratio_evidence_metadata,
)
from ktem_tests.finance_test_fixtures import quick_ratio_prompt as _quick_ratio_prompt


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


def test_extract_final_answer_text_removes_think_block_before_verification():
    answer = "<think>compute silently</think>\nFinal answer: Revenue was $10 million."

    assert extract_final_answer_text(answer) == "Revenue was $10 million."


def test_clean_answer_text_keeps_markdown_final_answer_after_untagged_thought():
    answer = (
        "Thought Okay, I should inspect irrelevant scratch work first. "
        "Profit declined sharply.\n\n"
        "**Final Answer**: Revenue increased in 2026."
    )

    assert clean_answer_text(answer) == "Revenue increased in 2026."
    assert answer_claims(answer) == ["Revenue increased in 2026."]


def test_clean_answer_text_uses_last_answer_marker_after_analysis_prefix():
    answer = (
        "analysis: first inspect unrelated scratch reasoning. "
        "Profit declined sharply.\n\n"
        "answer: The paper proposes a retrieval reranker."
    )

    assert clean_answer_text(answer) == "The paper proposes a retrieval reranker."
    assert answer_claims(answer) == ["The paper proposes a retrieval reranker."]


def test_clean_answer_text_uses_last_answer_marker_inside_analysis_prefix():
    answer = (
        "analysis: answer: Bad draft from scratch reasoning.\n\n"
        "Final answer: The paper proposes a retrieval reranker."
    )

    assert clean_answer_text(answer) == "The paper proposes a retrieval reranker."
    assert answer_claims(answer) == ["The paper proposes a retrieval reranker."]


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
        "| Metric | Value |\n| --- | ---: |\n| Revenue | 42 |"
    )


def test_clean_answer_text_preserves_substantial_answer_before_late_answer_label():
    answer = (
        "The document is a project proposal for MARA, a local-first document "
        "question-answering workbench designed for mixed academic and technical "
        "documents.\n\n"
        "| Item | Summary |\n"
        "| --- | --- |\n"
        "| Self-RAG-style controller | Selects the answer route based on the query. |\n"
        "| Verification layer | Checks generated claims against retrieved evidence. |\n\n"
        "Answer: It is a project proposal."
    )

    cleaned = clean_answer_text(answer)

    assert "local-first document question-answering workbench" in cleaned
    assert "| Self-RAG-style controller |" in cleaned
    assert "Answer: It is a project proposal." not in cleaned


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
            verification_domain="finance",
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
            verification_domain="finance",
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
            verification_domain="finance",
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


def test_default_verifier_still_rejects_conflicting_numeric_claim():
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
    assert payload["guardrail_decision"]["action"] == "revise"


def test_default_verifier_supports_short_source_level_evidence():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="strict"),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "14864#source",
                    "file_id": "14864",
                    "text": "Yelp",
                    "source_backrefs": ["14864#source"],
                }
            ]
        },
        answer="Final answer: The source is Yelp.",
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["unsupported_claims"] == []
    assert payload["guardrail_decision"]["action"] == "return"


def test_summary_verifier_supports_source_paraphrase_with_salient_anchor():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="Summarize the selected source.",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": (
                        "Marvel Comics superhero Hawkeye is a master with the "
                        "bow and arrow. He also has a secret super-talent at "
                        "singing Ed Sheeran parodies. Jeremy Renner was a "
                        "guest on The Tonight Show, where he got behind the "
                        "piano to showcase some of his other skills. Those "
                        "talents include scarves, berets, trombone, and "
                        "opening a pickle jar. Renner has proved he is more "
                        "than a one-hit wonder by starring in Avengers films, "
                        "The Hurt Locker, Bourne, and Mission Impossible."
                    ),
                }
            ]
        },
        answer=(
            "Final answer: His versatility extends beyond acting, including "
            "musical and quirky talents."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["unsupported_claims"] == []
    assert payload["guardrail_decision"]["action"] == "return"


def test_summary_verifier_supports_structured_source_field_synthesis():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="Write an objective overview based only on the structured data.",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": (
                        "{'hours': {'Monday': '8:0-17:0', "
                        "'Tuesday': '8:0-17:0', 'Wednesday': '8:0-17:0', "
                        "'Thursday': '8:0-17:0', 'Friday': '8:0-17:0', "
                        "'Saturday': '8:0-17:0', 'Sunday': '8:0-17:0'}, "
                        "'attributes': {'OutdoorSeating': True, "
                        "'RestaurantsTakeOut': True, "
                        "'RestaurantsGoodForGroups': True, 'WiFi': 'no'}}"
                    ),
                }
            ]
        },
        answer=(
            "Final answer: Open daily from 8:00 AM to 5:00 PM, it provides "
            "outdoor seating, take-out options, and is suitable for groups."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["unsupported_claims"] == []
    assert payload["guardrail_decision"]["action"] == "return"


def test_summary_verifier_rejects_unanchored_structured_source_claim():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="Write an objective overview based only on the structured data.",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": (
                        "{'name': 'Backyard Bowls', 'attributes': "
                        "{'OutdoorSeating': True, 'WiFi': 'no'}}"
                    ),
                }
            ]
        },
        answer="Final answer: The restaurant offers valet parking and live jazz.",
    )

    assert payload["verify_decision"]["status"] == "unsupported"
    assert payload["verify_decision"]["unsupported_claims"] == [
        "The restaurant offers valet parking and live jazz."
    ]
    assert payload["guardrail_decision"]["action"] == "revise"


def test_strict_verifier_rejects_conflicting_year_on_same_event():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="When did the project launch?",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": "The project launched in 2024 after the pilot ended.",
                }
            ]
        },
        answer="Final answer: The project launched in 2025.",
    )

    assert payload["verify_decision"]["status"] == "unsupported"
    assert payload["verify_decision"]["unsupported_claims"] == [
        "The project launched in 2025."
    ]
    assert payload["guardrail_decision"]["action"] == "revise"


def test_strict_verifier_rejects_conflicting_direction_on_same_metric():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="Did revenue increase or decrease?",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": "Revenue increased to 42 million in 2024.",
                }
            ]
        },
        answer="Final answer: Revenue decreased to 42 million in 2024.",
    )

    assert payload["verify_decision"]["status"] == "unsupported"
    assert payload["verify_decision"]["unsupported_claims"] == [
        "Revenue decreased to 42 million in 2024."
    ]
    assert payload["guardrail_decision"]["action"] == "revise"


def test_answer_claims_drop_evidence_commentary_after_answer_claim():
    answer = (
        "The Svalbard Global Seed Vault opened on February 26, 2008. "
        "This date is directly provided in the text, confirming the opening "
        "year and month. No additional calculations or interpretations are "
        "required."
    )

    assert answer_claims(answer) == [
        "The Svalbard Global Seed Vault opened on February 26, 2008."
    ]


def test_strict_verifier_ignores_evidence_commentary_after_supported_answer():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="When did the Svalbard Global Seed Vault open?",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": (
                        "Construction began on the Svalbard Global Seed Vault "
                        "on June 19, 2006, and the facility was opened on "
                        "February 26, 2008."
                    ),
                }
            ]
        },
        answer=(
            "Final answer: The Svalbard Global Seed Vault opened on "
            "February 26, 2008. This date is directly provided in the text, "
            "confirming the opening year and month. No additional "
            "calculations or interpretations are required."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["claims"] == [
        "The Svalbard Global Seed Vault opened on February 26, 2008."
    ]
    assert payload["verify_decision"]["unsupported_claims"] == []
    assert payload["guardrail_decision"]["action"] == "return"


def test_domain_verifier_requires_explicit_profile_flag():
    registry = DomainVerifierRegistry()

    assert registry.select(profile_flags={}) is registry.generic
    assert registry.select(profile_flags={"domain_verifier": "finance"}) is (
        registry.finance
    )


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
            verification_domain="finance",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.verify_decision.status == "unsupported"
    assert result.guardrail_decision.action == "abstain"
    assert result.answer
