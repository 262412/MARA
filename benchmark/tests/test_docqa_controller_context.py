from benchmark.docqa_controller_context import controller_request_context
from benchmark.schemas import BenchmarkConfig, BenchmarkExample


def test_ragtruth_benchmark_contract_constrains_controller_to_text_generation(
    tmp_path,
):
    example = BenchmarkExample(
        example_id="ex",
        document_id="doc",
        question="Is the response supported?",
        answers=['{"hallucination list": []}'],
        answer_type="verification",
        metadata={
            "dataset_family": "hallucination_verification",
            "source_info": "Revenue increased.",
            "response": "Revenue increased.",
        },
    )
    config = BenchmarkConfig(
        suite_name="stat-ragtruth-all-n50-shard00of6",
        output_dir=tmp_path,
        controller_mode="llm",
        route_policy="auto",
    )

    context = controller_request_context(
        example,
        config,
        lambda key: getattr(config, key, None),
    )

    assert context["verification_domain"] == "ragtruth"
    assert context["allowed_routes"] == ["doc_text"]
    assert context["verification_mode"] == "off"
    assert '"hallucination list"' in context["prompt"]


def test_qasper_runtime_task_type_does_not_expose_gold_answer_category(tmp_path):
    example = BenchmarkExample(
        example_id="ex",
        document_id="paper",
        question="What was the baseline?",
        answers=["unanswerable"],
        answer_type="unanswerable",
        metadata={"dataset_family": "scientific_qa"},
    )
    config = BenchmarkConfig(
        suite_name="qasper-typed",
        output_dir=tmp_path,
    )

    context = controller_request_context(
        example,
        config,
        lambda key: getattr(config, key, None),
    )

    assert context["verification_domain"] == "qasper"
    assert context["verification_mode"] == "strict"
    assert context["task_type"] == "qasper_qa"
    assert "unanswerable" not in context["task_type"]


def test_mmdoc_benchmark_defaults_to_strict_visual_verification(tmp_path):
    example = BenchmarkExample(
        example_id="ex",
        document_id="report",
        question="How did shareholder return change from 2017 to 2021?",
        answers=["It peaked and then declined."],
        answer_type="descriptive",
        metadata={"dataset_family": "multimodal_doc_qa"},
    )
    config = BenchmarkConfig(
        suite_name="mmdocrag-dev15",
        output_dir=tmp_path,
    )

    context = controller_request_context(
        example,
        config,
        lambda key: getattr(config, key, None),
    )

    assert context["verification_domain"] == "mmdocrag"
    assert context["verification_mode"] == "strict"
