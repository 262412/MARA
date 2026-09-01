from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit

from benchmark.artifact_publication import publish_artifact_contract

CORE_STAGES = (
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
)


def _fixture_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _evidence() -> dict[str, Any]:
    return {
        "canonical_id": "span:paper:s1",
        "source_id": "paper",
        "page_label": "1",
        "span_id": "s1",
        "evidence_level": "span",
        "text": "The paper reports the result.",
    }


def _prediction(requirements: list[str]) -> dict[str, Any]:
    item = _evidence()
    metadata: dict[str, Any] = {stage: [item] for stage in CORE_STAGES}
    metadata.update(
        {
            "ranking_trace": {"backend_execution": False},
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:answer",
                        "role": "support",
                        "required": True,
                        "status": "filled",
                        "evidence_ids": ["span:paper:s1"],
                    }
                ]
            },
        }
    )
    return {
        "example_id": "smoke",
        "document_id": "paper",
        "document_ids": ["paper"],
        "question": "What result is reported?",
        "answer_type": "free_text",
        "gold_answers": ["The result."],
        "gold_evidence": [{"document_id": "paper", "page": 1}],
        "gold_source_ids": ["paper"],
        "gold_evidence_texts": ["The paper reports the result."],
        "source_identity_crosswalk": [
            {
                "canonical_dataset_id": "paper",
                "runtime_file_id": "paper-runtime",
                "runtime_source_id": "paper-runtime",
                "document_path": "/datasets/paper.pdf",
                "filename": "paper.pdf",
                "aliases": ["paper"],
            }
        ],
        "predicted_answer": "The result.",
        "answer_for_scoring": "The result.",
        "example_metadata": {
            "contract_smoke_requirements": requirements,
        },
        "evidence_metadata": metadata,
    }


def _write_run(
    run_dir: Path,
    *,
    predictions: list[dict[str, Any]],
    artifact_detail: str = "full",
) -> None:
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": artifact_detail}),
        encoding="utf-8",
    )
    (run_dir / "predictions.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in predictions),
        encoding="utf-8",
    )
    publish_artifact_contract(run_dir)


def _attach_terminal_commit(prediction: dict[str, Any]) -> None:
    terminal_commit = build_terminal_semantic_commit(
        "yes",
        {
            "status": "supported",
            "action": "return",
            "canonical_answer_polarity": "yes",
            "verified_citations": ["span:paper:s1"],
        },
        {"status": "ok", "action": "return"},
        {
            "items": [_evidence()],
            "metadata": {"verified_claim_support_evidence": [_evidence()]},
        },
        presentation_answer="yes",
    ).as_dict()
    prediction["engine_terminal_state"]["terminal_semantic_commit"] = terminal_commit
    prediction["engine_terminal_commit"] = terminal_commit
    prediction["terminal_semantic_commit"] = terminal_commit
