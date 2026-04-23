from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _to_slug(text: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in text.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "benchmark"


def write_reports(
    report: dict[str, Any], output_dir: str | Path, suite_name: str
) -> Path:
    output_dir = Path(output_dir).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"{timestamp}_{_to_slug(suite_name)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.json"
    predictions_path = run_dir / "predictions.json"
    documents_path = run_dir / "documents.json"
    markdown_path = run_dir / "report.md"

    summary_path.write_text(
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    predictions_path.write_text(
        json.dumps(report["predictions"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    documents_path.write_text(
        json.dumps(report["documents"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    markdown = [
        f"# {report['summary']['suite_name']}",
        "",
        f"- Dataset: `{report['summary']['dataset_name']}`",
        f"- Examples: `{report['summary']['num_examples']}`",
        f"- Documents: `{report['summary']['num_documents']}`",
        f"- EM: `{report['summary']['avg_em']}`",
        f"- F1: `{report['summary']['avg_f1']}`",
        f"- ANLS: `{report['summary']['avg_anls']}`",
        f"- Page Hit: `{report['summary']['avg_page_hit']}`",
        f"- Citation Recall: `{report['summary']['avg_citation_recall']}`",
        f"- Element Hit: `{report['summary'].get('avg_element_hit')}`",
        f"- Span Recall: `{report['summary'].get('avg_span_recall')}`",
        f"- Formula Match: `{report['summary'].get('avg_formula_match')}`",
        f"- Numeric Match: `{report['summary'].get('avg_numeric_match')}`",
        f"- Avg Retrieval Seconds: `{report['summary']['avg_retrieval_seconds']}`",
        f"- Avg Generation Seconds: `{report['summary']['avg_generation_seconds']}`",
        "",
        "## Files",
        "",
        f"- Summary: `{summary_path}`",
        f"- Predictions: `{predictions_path}`",
        f"- Documents: `{documents_path}`",
    ]
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")
    return run_dir
