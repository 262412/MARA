from typing import Any

from benchmark.evidence_adapters import (
    normalize_gold_evidence,
    normalize_gold_evidence_record,
)
from benchmark.schemas import BenchmarkExample


def _example(**overrides):
    payload: dict[str, Any] = {
        "example_id": "ex-1",
        "document_id": "doc-1",
        "document_ids": [],
        "question": "Question?",
        "answers": ["answer"],
        "evidence_pages": [],
        "evidence_sources": [],
        "gold_evidence": [],
        "metadata": {},
    }
    payload.update(overrides)
    return BenchmarkExample(**payload)


def test_normalizes_page_and_source_evidence():
    evidence = normalize_gold_evidence(
        _example(
            evidence_pages=[10],
            evidence_sources=["doc.pdf#page:10"],
            gold_evidence=[{"page": "10", "text": "Revenue increased."}],
        )
    )

    assert evidence[0].page_label == "10"
    assert evidence[0].source == "doc.pdf#page:10"
    assert evidence[0].span_text == "Revenue increased."


def test_normalizes_raw_page_span_evidence_record():
    evidence = normalize_gold_evidence_record(
        {"document_id": "amd-2021", "page": 58, "span": "cash flow"}
    )

    assert evidence.source_id == "amd-2021"
    assert evidence.page_label == "58"
    assert evidence.text_span == "cash flow"
    assert evidence.citation == "amd-2021#page:58"
    assert evidence.locator_kind == "page"


def test_normalizes_raw_source_level_evidence_record():
    evidence = normalize_gold_evidence_record(
        {"document_id": "14864", "span": "Yelp", "citation": "14864#source"}
    )

    assert evidence.source_id == "14864"
    assert evidence.page_label is None
    assert evidence.text_span == "Yelp"
    assert evidence.citation == "14864#source"
    assert evidence.locator_kind == "source"


def test_normalizes_qasper_span_evidence_without_page_requirement():
    evidence = normalize_gold_evidence(
        _example(gold_evidence=[{"text": "The proposed method improves recall."}])
    )

    assert evidence[0].span_text == "The proposed method improves recall."
    assert evidence[0].page_label is None


def test_normalizes_ragtruth_hallucination_labels():
    evidence = normalize_gold_evidence(
        _example(gold_evidence=[{"text": "Unsupported claim", "label": "unsupported"}])
    )

    assert evidence[0].support_label == "unsupported"


def test_normalizes_alce_citation_targets():
    evidence = normalize_gold_evidence(
        _example(gold_evidence=[{"citation": "doc-7", "text": "Attributable answer"}])
    )

    assert evidence[0].source == "doc-7"
    assert evidence[0].span_text == "Attributable answer"


def test_extracts_page_label_from_hash_page_locator():
    evidence = normalize_gold_evidence(
        _example(gold_evidence=[{"citation": "doc.pdf#page=12"}])
    )

    assert evidence[0].source == "doc.pdf#page=12"
    assert evidence[0].page_label == "12"


def test_extracts_page_label_from_short_page_locator():
    evidence = normalize_gold_evidence(
        _example(gold_evidence=[{"source": "paper p. 7"}])
    )

    assert evidence[0].source == "paper p. 7"
    assert evidence[0].page_label == "7"


def test_extracts_page_label_from_document_colon_locator():
    evidence = normalize_gold_evidence(
        _example(gold_evidence=[{"source": "document.pdf:23"}])
    )

    assert evidence[0].source == "document.pdf:23"
    assert evidence[0].page_label == "23"
