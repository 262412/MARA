import json

from benchmark.artifact_rescoring import rescore_artifact_run


def test_rescore_artifact_recomputes_indexed_inline_citation_metrics(tmp_path):
    source_run = tmp_path / "source-run"
    source_run.mkdir()
    (source_run / "summary.json").write_text(
        json.dumps(
            {
                "suite_name": "Original Suite",
                "dataset_name": "alce-asqa",
                "num_examples": 1,
                "num_documents": 1,
                "avg_citation_inline_recall": 0.0,
            }
        ),
        encoding="utf-8",
    )
    (source_run / "predictions.jsonl").write_text(
        json.dumps(
            {
                "example_id": "ex-1",
                "route": "controller_auto",
                "benchmark_role": "qa_quality",
                "predicted_answer": "Waxahachie, Texas [1].",
                "gold_answers": ["Waxahachie, Texas"],
                "gold_pages": [],
                "predicted_pages": [],
                "predicted_sources": ["doc#source"],
                "predicted_citations": [],
                "gold_sources": ["doc#source"],
                "gold_evidence": [
                    {
                        "document_id": "doc",
                        "citation": "doc#source",
                        "span": "Waxahachie, Texas",
                    }
                ],
                "retrieved_hits": [
                    {
                        "document_id": "doc",
                        "source_id": "doc",
                        "text": "Waxahachie is a city in Texas.",
                        "source_backrefs": ["doc#source"],
                    }
                ],
                "metrics": {
                    "citation_inline_recall": 0.0,
                    "citation_inline_precision": 0.0,
                    "citation_recall": 0.0,
                    "citation_precision": 0.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source_run / "documents.json").write_text("[]", encoding="utf-8")

    output_dir = tmp_path / "rescored"
    rescored_run = rescore_artifact_run(source_run, output_dir)

    summary = json.loads((rescored_run / "summary.json").read_text(encoding="utf-8"))
    prediction = json.loads(
        (rescored_run / "predictions.jsonl").read_text(encoding="utf-8")
    )

    assert prediction["predicted_citations"] == ["doc#source"]
    assert prediction["metrics"]["citation_inline_recall"] == 1.0
    assert prediction["metrics"]["citation_inline_precision"] == 1.0
    assert prediction["metrics"]["citation_recall"] == 1.0
    assert prediction["metrics"]["citation_precision"] == 1.0
    assert summary["avg_citation_inline_recall"] == 1.0
