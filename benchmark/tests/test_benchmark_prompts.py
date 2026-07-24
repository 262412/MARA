import ast
from typing import Any

from benchmark.benchmark_prompts import BENCHMARK_PROMPT_MARKER, build_benchmark_prompt
from benchmark.schemas import BenchmarkConfig, BenchmarkExample


def _example(**overrides: Any) -> BenchmarkExample:
    payload: dict[str, Any] = {
        "example_id": "ex",
        "document_id": "doc",
        "question": "What did the filing say about revenue?",
        "answers": ["Revenue increased."],
    }
    payload.update(overrides)
    return BenchmarkExample(**payload)


def test_raw_prompt_policy_preserves_dataset_question(tmp_path):
    config = BenchmarkConfig(
        suite_name="financebench",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="raw",
    )

    prompt = build_benchmark_prompt(_example(), config, dataset_name="financebench")

    assert prompt.policy == "raw"
    assert prompt.profile == "raw"
    assert prompt.raw_question == "What did the filing say about revenue?"
    assert prompt.benchmark_question == "What did the filing say about revenue?"
    assert prompt.runtime_prompt == "What did the filing say about revenue?"
    assert prompt.retrieval_query == "What did the filing say about revenue?"


def test_gold_answer_policy_uses_no_think_answer_only_prompt(tmp_path):
    config = BenchmarkConfig(
        suite_name="financebench",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
    )

    prompt = build_benchmark_prompt(
        _example(answer_type="numeric"),
        config,
        dataset_name="financebench",
    )

    assert prompt.policy == "gold_answer_v1"
    assert prompt.runtime_prompt.startswith("/no_think\n")
    assert "Benchmark gold-answer contract:" in prompt.runtime_prompt
    assert "Return only the gold-answer value" in prompt.runtime_prompt
    assert "Do not provide explanation" in prompt.runtime_prompt
    assert "Question: What did the filing say about revenue?" in prompt.runtime_prompt
    assert prompt.runtime_prompt.rstrip().endswith("Answer:")
    assert prompt.retrieval_query == "What did the filing say about revenue?"


def test_gold_answer_policy_separates_ragtruth_task_and_retrieval_budgets(tmp_path):
    long_question = (
        "Original source prompt. "
        + ("This passage is intentionally long and repeats support text. " * 300)
        + "UNIQUE_RAGTRUTH_TAIL_SHOULD_BE_TRUNCATED"
    )
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
        benchmark_no_think=True,
        max_context_length=1200,
    )

    prompt = build_benchmark_prompt(
        _example(
            question=long_question,
            answer_type="verification",
            metadata={
                "source_info": long_question,
                "response": "The answer contains one unsupported claim.",
            },
        ),
        config,
        dataset_name="ragtruth",
    )

    assert prompt.raw_question == long_question.strip()
    assert len(prompt.benchmark_question) <= 1200
    assert len(prompt.retrieval_query) <= 1200
    assert "[truncated to fit benchmark prompt budget]" in prompt.benchmark_question
    assert prompt.runtime_prompt.startswith("/no_think\n")
    assert "Below are related passages:" in prompt.runtime_prompt
    assert "Below is an answer:" in prompt.runtime_prompt
    assert '"hallucination list"' in prompt.runtime_prompt
    assert 1200 < len(prompt.runtime_prompt.removeprefix("/no_think\n")) <= 12000
    assert "Original source prompt." in prompt.runtime_prompt
    assert "UNIQUE_RAGTRUTH_TAIL_SHOULD_BE_TRUNCATED" not in prompt.runtime_prompt
    assert prompt.runtime_prompt.rstrip().endswith("Answer:")


def test_ragtruth_task_prompt_keeps_complete_source_and_response_under_task_budget(
    tmp_path,
):
    source = "Supported source sentence. " * 100
    response = "Supported response sentence. " * 20
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
        max_context_length=2000,
    )

    prompt = build_benchmark_prompt(
        _example(
            answer_type="verification",
            metadata={"source_info": source, "response": response},
        ),
        config,
        dataset_name="ragtruth",
    )

    assert len(prompt.runtime_prompt) > config.max_context_length
    assert source.strip() in prompt.runtime_prompt
    assert response.strip() in prompt.runtime_prompt


def test_ragtruth_truncated_response_never_injects_non_response_span(tmp_path):
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
        max_context_length=900,
    )
    prompt = build_benchmark_prompt(
        _example(
            answer_type="verification",
            metadata={
                "source_info": "Supported source text. " * 100,
                "response": "Unsupported response text. " * 100,
            },
        ),
        config,
        dataset_name="ragtruth",
    )

    response_block = prompt.runtime_prompt.split("Below is an answer:\n", 1)[1]
    response_block = response_block.split(
        'Return exactly one JSON object with the key "hallucination list".',
        1,
    )[0]
    assert "[truncated to fit benchmark prompt budget]" not in response_block


def test_ragtruth_summary_source_budget_keeps_response_relevant_tail(tmp_path):
    source = (
        "Opening source fact. "
        + ("Irrelevant middle material about unrelated topics. " * 250)
        + (
            "Joint U.S.-Mexican patrols along the Rio Grande could make the "
            "border safer, and 2,500 migrants are encountered every weekend."
        )
    )
    response = (
        "Joint U.S.-Mexican patrols along the Rio Grande could make the border "
        "safer, and 2,500 migrants are encountered every weekend."
    )
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
        max_context_length=900,
    )

    prompt = build_benchmark_prompt(
        _example(
            answer_type="verification",
            metadata={
                "task_type": "Summary",
                "source_info": source,
                "response": response,
            },
        ),
        config,
        dataset_name="ragtruth",
    )

    source_block = prompt.runtime_prompt.split("Below is the original source:\n", 1)[
        1
    ].split("Below is a summary or response:\n", 1)[0]
    assert "2,500 migrants are encountered every weekend" in source_block
    assert len(source_block) < len(source)


def test_ragtruth_data2txt_source_truncation_preserves_valid_mapping(tmp_path):
    source = {
        "name": "Silvergreens",
        "hours": {"Sunday": "9:0-21:0"},
        "attributes": {
            "WiFi": "free",
            "RestaurantsGoodForGroups": True,
            "RestaurantsReservations": False,
        },
        "review_info": [
            {
                "review_text": (
                    "The restaurant provides free Wi-Fi and is good for groups. "
                    + ("Long but irrelevant review details. " * 400)
                )
            }
        ],
    }
    response = (
        "The restaurant provides free Wi-Fi and is good for groups, but does "
        "not take reservations."
    )
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
        max_context_length=900,
    )

    prompt = build_benchmark_prompt(
        _example(
            answer_type="verification",
            metadata={
                "task_type": "Data2txt",
                "source_info": str(source),
                "response": response,
            },
        ),
        config,
        dataset_name="ragtruth",
    )

    source_block = prompt.runtime_prompt.split(
        "Below is the structured JSON data:\n", 1
    )[1].split("Below is an overview of the data:\n", 1)[0]
    parsed = ast.literal_eval(source_block.strip())
    assert parsed["attributes"]["WiFi"] == "free"
    assert parsed["attributes"]["RestaurantsReservations"] is False
    assert parsed["hours"]["Sunday"] == "9:0-21:0"


def test_benchmark_v1_uses_benchmark_prompt_contract_not_mara_marker(tmp_path):
    config = BenchmarkConfig(
        suite_name="qasper",
        output_dir=tmp_path / "out",
    )

    prompt = build_benchmark_prompt(_example(), config, dataset_name="qasper")

    assert prompt.policy == "benchmark_v1"
    assert prompt.profile == "concise_grounded_qa"
    assert prompt.raw_question == "What did the filing say about revenue?"
    assert prompt.benchmark_question == "What did the filing say about revenue?"
    assert prompt.retrieval_query == "What did the filing say about revenue?"
    assert prompt.runtime_prompt.startswith(BENCHMARK_PROMPT_MARKER)
    assert "Question: What did the filing say about revenue?" in prompt.runtime_prompt
    assert BENCHMARK_PROMPT_MARKER in prompt.runtime_prompt
    assert "Start with the direct answer" in prompt.runtime_prompt
    assert "Do not include hidden reasoning" in prompt.runtime_prompt
    assert "Start with the direct answer" not in prompt.retrieval_query
    assert "Answer formatting requirements:" not in prompt.runtime_prompt
    assert "Return the final answer as Markdown" not in prompt.runtime_prompt


def test_alce_prompt_uses_official_search_result_citation_framework(tmp_path):
    config = BenchmarkConfig(
        suite_name="alce",
        output_dir=tmp_path / "out",
    )

    prompt = build_benchmark_prompt(
        _example(
            question="Which city hosted the event?",
            answer_type="citation_qa",
        ),
        config,
        dataset_name="alce",
    )

    assert prompt.prompt_source == "princeton-nlp/ALCE prompts/asqa_default.json"
    assert "using only the provided search results" in prompt.runtime_prompt
    assert "cite them properly" in prompt.runtime_prompt
    assert "Question: Which city hosted the event?" in prompt.runtime_prompt
    assert prompt.runtime_prompt.rstrip().endswith("Answer:")
    assert "Answer formatting requirements:" not in prompt.runtime_prompt


def test_alce_qampari_prompt_requires_comma_separated_answer_list(tmp_path):
    config = BenchmarkConfig(
        suite_name="alce-qampari",
        output_dir=tmp_path / "out",
    )

    prompt = build_benchmark_prompt(
        _example(
            question="What manga was drawn by Ryoichi Ikegami?",
            answer_type="list_qa",
            metadata={"alce_task": "qampari"},
        ),
        config,
        dataset_name="alce-qampari",
    )

    assert prompt.prompt_source == "princeton-nlp/ALCE prompts/qampari_default.json"
    assert "comma-separated list" in prompt.runtime_prompt
    assert "Do not write a paragraph" in prompt.runtime_prompt
    assert "Question: What manga was drawn by Ryoichi Ikegami?" in prompt.runtime_prompt
    assert prompt.runtime_prompt.rstrip().endswith("Answer:")


def test_ragtruth_prompt_uses_official_hallucination_json_contract(tmp_path):
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
    )
    example = _example(
        question="Is the answer fully supported?",
        answer_type="verification",
        answers=["The answer says revenue doubled."],
        metadata={
            "task_type": "QA",
            "source_info": "Revenue increased from 10 to 12.",
            "response": "Revenue doubled.",
        },
    )

    prompt = build_benchmark_prompt(example, config, dataset_name="ragtruth")

    assert prompt.prompt_source == "ParticleMedia/RAGTruth baseline/dataset.py"
    assert "Below is a question:" in prompt.runtime_prompt
    assert "Below are related passages:" in prompt.runtime_prompt
    assert "Below is an answer:" in prompt.runtime_prompt
    assert '"hallucination list"' in prompt.runtime_prompt
    assert "Revenue increased from 10 to 12." in prompt.runtime_prompt
    assert "Revenue doubled." in prompt.runtime_prompt


def test_ragtruth_prompt_does_not_repeat_source_generation_instruction(tmp_path):
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
    )
    example = _example(
        question="Briefly answer the following question: benefits of cupping massage",
        answer_type="verification",
        metadata={
            "task_type": "QA",
            "source_info": "Cupping can improve circulation.",
            "response": "Cupping cures every disease.",
        },
    )

    prompt = build_benchmark_prompt(example, config, dataset_name="ragtruth")

    assert "Briefly answer the following question" not in prompt.runtime_prompt
    assert prompt.runtime_prompt.index("Detect exact response spans") < (
        prompt.runtime_prompt.index("Below are related passages:")
    )
    assert prompt.runtime_prompt.rstrip().endswith(
        'Return exactly one JSON object with the key "hallucination list".\nAnswer:'
    )


def test_qasper_prompt_uses_paper_context_short_answer_contract(tmp_path):
    config = BenchmarkConfig(
        suite_name="qasper",
        output_dir=tmp_path / "out",
    )

    prompt = build_benchmark_prompt(
        _example(
            question="Which baseline model is compared?",
            answer_type="evidence_qa",
        ),
        config,
        dataset_name="qasper",
    )

    assert prompt.prompt_source == "allenai/qasper-led-baseline dataset contract"
    assert "provided research paper context or evidence" in prompt.runtime_prompt
    assert "Return only the answer span" in prompt.runtime_prompt
    assert "unanswerable" in prompt.runtime_prompt


def test_benchmark_v1_requires_short_atomic_and_calculation_answers(tmp_path):
    config = BenchmarkConfig(
        suite_name="mixed-domain",
        output_dir=tmp_path / "out",
    )

    prompt = build_benchmark_prompt(
        _example(
            question="What is the year-end net working capital?",
            answer_type="numeric",
        ),
        config,
        dataset_name="mixed-domain",
    )

    assert "single name, date, time, amount, count, or yes/no" in prompt.runtime_prompt
    assert "return only that value" in prompt.runtime_prompt
    assert "For numeric or calculation questions" in prompt.runtime_prompt
    assert "final value first" in prompt.runtime_prompt
    assert "one short formula or source phrase" in prompt.runtime_prompt
    assert "name the missing operand" in prompt.runtime_prompt
    assert "Do not use tables unless" in prompt.runtime_prompt


def test_benchmark_prompt_uses_manifest_question_override(tmp_path):
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_profile="guardrail_grounded_qa",
    )
    example = _example(
        question="User-side prompt with long generation instructions.",
        metadata={
            "benchmark_question": "Is the response fully supported by the source?",
            "retrieval_query": "source support for response",
        },
    )

    prompt = build_benchmark_prompt(example, config, dataset_name="ragtruth")

    assert prompt.profile == "guardrail_grounded_qa"
    assert prompt.raw_question == "User-side prompt with long generation instructions."
    assert prompt.benchmark_question == "Is the response fully supported by the source?"
    assert prompt.retrieval_query == "source support for response"
    assert prompt.runtime_prompt.startswith(BENCHMARK_PROMPT_MARKER)
    assert "Below is a question:" in prompt.runtime_prompt
    assert "Is the response fully supported by the source?" in prompt.runtime_prompt


def test_auto_profile_selects_dataset_specific_generic_contracts(tmp_path):
    config = BenchmarkConfig(suite_name="suite", output_dir=tmp_path / "out")

    assert (
        build_benchmark_prompt(
            _example(answer_type="citation_qa"),
            config,
            dataset_name="alce",
        ).profile
        == "citation_grounded_qa"
    )
    assert (
        build_benchmark_prompt(
            _example(answer_type="verification"),
            config,
            dataset_name="ragtruth",
        ).profile
        == "guardrail_grounded_qa"
    )
    assert (
        build_benchmark_prompt(
            _example(modality="page_image"),
            config,
            dataset_name="slidevqa",
        ).profile
        == "visual_grounded_qa"
    )


def test_ragtruth_gold_answer_policy_keeps_source_and_response(tmp_path):
    config = BenchmarkConfig(
        suite_name="ragtruth",
        output_dir=tmp_path / "out",
        benchmark_prompt_policy="gold_answer_v1",
    )
    example = _example(
        question="What happened to revenue?",
        answer_type="verification",
        metadata={
            "dataset_family": "hallucination_verification",
            "task_type": "QA",
            "source_info": "Revenue increased from 10 to 12.",
            "response": "Revenue doubled.",
        },
    )

    prompt = build_benchmark_prompt(example, config, dataset_name="ragtruth")

    assert prompt.prompt_source == "ParticleMedia/RAGTruth baseline/dataset.py"
    assert "Below are related passages:" in prompt.runtime_prompt
    assert "Revenue increased from 10 to 12." in prompt.runtime_prompt
    assert "Below is an answer:" in prompt.runtime_prompt
    assert "Revenue doubled." in prompt.runtime_prompt
    assert '"hallucination list"' in prompt.runtime_prompt
