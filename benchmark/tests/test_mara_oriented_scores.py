from benchmark.mara_oriented_scores import mara_oriented_metrics


def test_mara_score_rewards_supported_cited_answer_when_lexical_f1_is_low():
    metrics = mara_oriented_metrics(
        {
            "metrics": {
                "em": 0.0,
                "f1": 0.05,
                "anls": 0.0,
                "page_hit": 1.0,
                "span_recall": 1.0,
                "citation_recall": 1.0,
                "citation_precision": 1.0,
                "unsupported_claim_rate": 0.0,
                "contradiction_count": 0.0,
                "false_abstention": 0.0,
            },
            "diagnostics": {"controller_route_match": 1.0},
        },
        dataset_name="qasper-formal",
    )

    assert metrics["mara_answer_score"] == 0.05
    assert metrics["mara_evidence_score"] == 1.0
    assert metrics["mara_citation_score"] == 1.0
    assert metrics["mara_groundedness_score"] == 1.0
    assert metrics["mara_abstention_score"] == 1.0
    assert metrics["mara_controller_score"] == 1.0
    assert metrics["mara_format_score"] is None
    assert metrics["mara_score"] == 0.85


def test_mara_score_excludes_missing_optional_controller_signal_from_denominator():
    metrics = mara_oriented_metrics(
        {
            "metrics": {
                "em": 0.0,
                "f1": 0.05,
                "anls": 0.0,
                "page_hit": 1.0,
                "span_recall": 1.0,
                "citation_recall": 1.0,
                "citation_precision": 1.0,
                "unsupported_claim_rate": 0.0,
                "contradiction_count": 0.0,
                "false_abstention": 0.0,
            },
            "diagnostics": {},
        },
        dataset_name="qasper-formal",
    )

    assert metrics["mara_controller_score"] is None
    assert metrics["mara_score"] == 0.8417


def test_ragtruth_profile_prioritizes_groundedness_over_gold_answer_style():
    metrics = mara_oriented_metrics(
        {
            "metrics": {
                "em": 0.0,
                "f1": 0.0,
                "span_recall": 1.0,
                "unsupported_claim_rate": 0.0,
                "contradiction_count": 0.0,
                "abstention_correctness": 1.0,
            },
            "diagnostics": {"controller_route_match": 1.0},
        },
        dataset_name="ragtruth-plan5",
    )

    assert metrics["mara_answer_score"] is None
    assert metrics["mara_evidence_score"] == 1.0
    assert metrics["mara_groundedness_score"] == 1.0
    assert metrics["mara_abstention_score"] == 1.0
    assert metrics["mara_score"] == 1.0


def test_visual_profile_uses_multimodal_evidence_support():
    metrics = mara_oriented_metrics(
        {
            "metrics": {
                "em": 0.0,
                "f1": 0.2,
                "page_hit": 1.0,
                "multimodal_answer_support": 1.0,
                "citation_recall": 0.5,
                "citation_precision": 0.5,
                "unsupported_claim_rate": 0.0,
                "contradiction_count": 0.0,
                "false_abstention": 0.0,
            },
            "diagnostics": {"controller_route_match": 1.0},
        },
        dataset_name="mmdocrag-visual",
    )

    assert metrics["mara_answer_score"] == 0.2
    assert metrics["mara_evidence_score"] == 1.0
    assert metrics["mara_citation_score"] == 0.5
    assert metrics["mara_score"] is not None
    assert metrics["mara_score"] > 0.75
