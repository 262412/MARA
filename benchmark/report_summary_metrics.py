from __future__ import annotations

from typing import Any


def diagnostic_metric_lines(summary: dict[str, Any]) -> list[str]:
    return [
        f"- ANLS: `{summary.get('avg_anls')}`",
        f"- Page Hit: `{summary.get('avg_page_hit')}`",
        f"- Strict Page Hit: `{summary.get('avg_strict_page_hit')}`",
        "- Equivalent-Evidence Page Hit: "
        f"`{summary.get('avg_equivalent_evidence_page_hit')}`",
        f"- Citation Recall: `{summary.get('avg_citation_recall')}`",
        "- Citation Metadata Recall: "
        f"`{summary.get('avg_citation_metadata_recall')}`",
        "- Citation Metadata Precision: "
        f"`{summary.get('avg_citation_metadata_precision')}`",
        f"- Citation Inline Recall: `{summary.get('avg_citation_inline_recall')}`",
        f"- Citation Inline Precision: `{summary.get('avg_citation_inline_precision')}`",
        f"- Element Hit: `{summary.get('avg_element_hit')}`",
        f"- Element Locator Hit: `{summary.get('avg_element_locator_hit')}`",
        f"- Table Hit: `{summary.get('avg_table_hit')}`",
        f"- Figure Hit: `{summary.get('avg_figure_hit')}`",
        f"- Formula Hit: `{summary.get('avg_formula_hit')}`",
        f"- Slide Hit: `{summary.get('avg_slide_hit')}`",
        f"- Span Recall: `{summary.get('avg_span_recall')}`",
        f"- Formula Match: `{summary.get('avg_formula_match')}`",
        f"- Numeric Match: `{summary.get('avg_numeric_match')}`",
        f"- Abstention Rate: `{summary.get('avg_abstention_rate')}`",
        f"- False Abstention: `{summary.get('avg_false_abstention')}`",
        "- Markdown Table Renderable: "
        f"`{summary.get('avg_markdown_table_renderable')}`",
        f"- LaTeX Renderable: `{summary.get('avg_latex_renderable')}`",
        f"- Rewrite Skipped: `{summary.get('avg_rewrite_skipped')}`",
        "- Guardrail Expectation Match: "
        f"`{summary.get('avg_guardrail_expectation_match')}`",
        f"- Avg Parse Seconds: `{summary.get('avg_parse_seconds')}`",
        f"- Avg Index Seconds: `{summary.get('avg_index_seconds')}`",
        f"- Avg Retrieval Seconds: `{summary.get('avg_retrieval_seconds')}`",
        f"- Avg Generation Seconds: `{summary.get('avg_generation_seconds')}`",
        f"- Cache Mode: `{summary.get('cache_mode')}`",
        f"- Parse Cache Hit Rate: `{summary.get('parse_cache_hit_rate')}`",
        f"- Embedding Cache Hit Rate: `{summary.get('embedding_cache_hit_rate')}`",
        f"- Executed Routes: `{summary.get('num_executed_routes')}`",
        f"- Skipped Routes: `{summary.get('num_skipped_routes')}`",
    ]
