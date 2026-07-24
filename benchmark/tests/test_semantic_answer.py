import json

import benchmark.semantic_answer as semantic_module
from benchmark.semantic_answer import semantic_answer_metrics
from benchmark.summary import add_mara_summary_fields


def test_boolean_semantic_score_accepts_qasper_boolean_aliases():
    metrics, metadata = semantic_answer_metrics(
        {
            "answer_type": "boolean",
            "predicted_answer": "yes",
            "gold_answers": ["true"],
            "example_metadata": {"dataset_family": "scientific_qa"},
        }
    )

    assert metrics == {
        "semantic_answer_precision": 1.0,
        "semantic_answer_recall": 1.0,
        "semantic_answer_f1": 1.0,
    }
    assert metadata["contract_id"] == "semantic_answer_claim_f1_v1"
    assert metadata["method"] == "deterministic_boolean"
    assert metadata["judge_status"] == "not_required"


def test_local_qwen_judge_uses_fixed_deterministic_json_contract(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        @staticmethod
        def read():
            result = {
                "gold_claim_count": 1,
                "supported_gold_claim_count": 1,
                "predicted_relevant_claim_count": 1,
                "supported_predicted_claim_count": 1,
                "core_contradiction": False,
            }
            return json.dumps(
                {"choices": [{"message": {"content": json.dumps(result)}}]}
            ).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(semantic_module.urllib.request, "urlopen", fake_urlopen)
    judge = semantic_module.LocalSemanticJudge(timeout_seconds=12)

    result = judge({"question": "What changed?"})

    assert result["core_contradiction"] is False
    assert captured["body"]["model"] == "Qwen/Qwen3-8B"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["messages"][0]["content"].startswith("/no_think")
    assert captured["timeout"] == 12


def test_semantic_judge_backend_accepts_canonical_local_alias():
    judge = semantic_module.semantic_judge_backend("local")

    assert isinstance(judge, semantic_module.LocalSemanticJudge)


def test_free_text_semantic_score_rewards_supported_explanation():
    def judge(_payload):
        return {
            "gold_claim_count": 1,
            "supported_gold_claim_count": 1,
            "predicted_relevant_claim_count": 2,
            "supported_predicted_claim_count": 2,
            "core_contradiction": False,
        }

    metrics, metadata = semantic_answer_metrics(
        {
            "question": "What happened to revenue?",
            "answer_type": "free_text",
            "predicted_answer": (
                "Revenue increased. The increase was driven by stronger demand."
            ),
            "gold_answers": ["Revenue increased"],
            "gold_evidence": [
                {"span": "Revenue increased because demand strengthened."}
            ],
        },
        judge=judge,
    )

    assert metrics["semantic_answer_f1"] == 1.0
    assert metadata["method"] == "local_claim_entailment"
    assert metadata["judge_status"] == "ok"
    assert metadata["prompt_contract"] == "semantic_claim_judge_prompt_v1"


def test_numeric_semantic_score_rejects_conflicting_unit_or_scale():
    metrics, metadata = semantic_answer_metrics(
        {
            "answer_type": "numeric",
            "predicted_answer": "$10 billion",
            "gold_answers": ["$10 million"],
        }
    )

    assert metrics["semantic_answer_f1"] == 0.0
    assert metadata["core_contradiction"] is True


def test_free_text_semantic_score_rejects_core_contradiction():
    def judge(_payload):
        return {
            "gold_claim_count": 1,
            "supported_gold_claim_count": 0,
            "predicted_relevant_claim_count": 1,
            "supported_predicted_claim_count": 0,
            "core_contradiction": True,
        }

    metrics, metadata = semantic_answer_metrics(
        {
            "question": "Did revenue rise?",
            "answer_type": "free_text",
            "predicted_answer": "Revenue declined.",
            "gold_answers": ["Revenue increased."],
        },
        judge=judge,
    )

    assert metrics["semantic_answer_f1"] == 0.0
    assert metadata["core_contradiction"] is True


def test_free_text_judge_failure_is_null_not_token_f1_fallback():
    def judge(_payload):
        raise ValueError("invalid judge JSON")

    metrics, metadata = semantic_answer_metrics(
        {
            "question": "What happened?",
            "answer_type": "free_text",
            "predicted_answer": "Revenue increased.",
            "gold_answers": ["Revenue increased."],
        },
        judge=judge,
    )

    assert metrics["semantic_answer_precision"] is None
    assert metrics["semantic_answer_recall"] is None
    assert metrics["semantic_answer_f1"] is None
    assert metadata["judge_status"] == "error"


def test_ragtruth_is_excluded_from_semantic_answer_f1():
    metrics, metadata = semantic_answer_metrics(
        {
            "answer_type": "verification",
            "predicted_answer": '{"hallucination list": []}',
            "gold_answers": ["The response under review."],
            "example_metadata": {"dataset_family": "hallucination_verification"},
        }
    )

    assert metrics["semantic_answer_f1"] is None
    assert metadata["judge_status"] == "not_applicable"


def test_summary_reports_semantic_score_and_judge_coverage_without_replacing_f1():
    predictions = [
        {
            "route": "text_rag",
            "benchmark_role": "qa_quality",
            "metrics": {"f1": 0.25, "semantic_answer_f1": 1.0},
            "semantic_answer_evaluation": {"judge_status": "ok"},
        },
        {
            "route": "text_rag",
            "benchmark_role": "qa_quality",
            "metrics": {"f1": 0.75, "semantic_answer_f1": None},
            "semantic_answer_evaluation": {"judge_status": "error"},
        },
    ]

    summary = add_mara_summary_fields({"dataset_name": "qasper"}, predictions)

    assert summary["avg_f1"] == 0.5
    assert summary["avg_semantic_answer_f1"] == 1.0
    assert summary["semantic_judge_coverage"] == 0.5
    assert summary["quality_avg_semantic_answer_f1"] == 1.0
    assert summary["answer_quality_contract"] == "semantic_answer_claim_f1_v1"
