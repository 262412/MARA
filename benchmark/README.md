# Benchmark

This is the first clean benchmark framework for this repo.

It is built around one normalized manifest format so we can compare:

- local `PDF / DOC / DOCX / PPT / PPTX` robustness
- `FinanceBench`
- `SlideVQA`
- future `MP-DocVQA / QASPER / DUDE` conversions without rewriting the runner

## What It Measures

- answer `EM`
- answer `F1`
- answer `ANLS`
- page hit rate when gold pages exist
- citation recall when gold evidence strings exist
- element hit and span recall when gold evidence carries element ids or spans
- formula normalized match and numeric tolerance
- abstention rate and false abstention, especially answers rewritten to "document evidence cannot support this answer"
- Markdown table renderability for table answers
- LaTeX delimiter compatibility for formula answers
- claim-verification guardrail behavior, including whether a supported answer was skipped or rewritten
- evidence metadata for image, figure, formula, and page-visual context reaching the answer path
- parse and indexing time per document
- retrieval and generation latency per example

## Manifest Format

Each example points to one local document:

```json
{
  "dataset_name": "format_robustness",
  "examples": [
    {
      "example_id": "pdf_1_0",
      "document_id": "pdf_1",
      "document_path": "data/test_documents/pdf/1_example.pdf",
      "format_type": "pdf",
      "question": "What is ...?",
      "answers": ["..."],
      "evidence_pages": [1],
      "evidence_sources": ["file.pdf#page:1"],
      "expected_formats": ["markdown_table", "latex"],
      "expected_guardrails": {
        "allow_abstention": false,
        "rewrite_skipped": true
      },
      "metadata": {}
    }
  ]
}
```

For route-matrix evaluation, use schema version 2:

```json
{
  "schema_version": 2,
  "dataset_name": "docqa_acceptance",
  "documents": [
    {
      "document_id": "paper",
      "path": "paper.pdf",
      "format_type": "pdf",
      "modality": "mixed"
    }
  ],
  "routes": [
    {
      "route_id": "direct_paste_document",
      "engine": "direct_paste",
      "scope": "document"
    },
    { "route_id": "oracle_page", "engine": "oracle_page", "scope": "page" },
    { "route_id": "docqa_page", "engine": "docqa_runtime", "scope": "page" },
    {
      "route_id": "docqa_document",
      "engine": "docqa_runtime",
      "scope": "document"
    },
    {
      "route_id": "docqa_multi_document",
      "engine": "docqa_runtime",
      "scope": "multi_document"
    }
  ],
  "examples": [
    {
      "example_id": "figure_1",
      "document_ids": ["paper"],
      "scope": "page",
      "modality": "figure",
      "answer_type": "descriptive",
      "question": "What structure is shown in Figure 1?",
      "answers": ["..."],
      "gold_evidence": [
        { "page": 1, "element_id": "figure-1", "citation": "paper#page:1" }
      ],
      "expected_formats": ["markdown_table"],
      "expected_guardrails": { "allow_abstention": false }
    }
  ]
}
```

Use `direct_paste_document` as the "user pasted all available text" baseline. The DocQA routes should beat it on questions that require citations, page scope, figure/formula evidence, or multi-document retrieval. `oracle_page` is an upper-bound diagnostic route: it answers from the gold page context and helps separate retrieval failures from generation or formatting failures.

## Quick Start

Build a manifest from the local format-robustness folder:

```powershell
python -m benchmark normalize-format-robustness `
  --source-dir data/test_documents `
  --output benchmark/manifests/format_robustness.json
```

Run the benchmark:

```powershell
python -m benchmark run `
  --manifest benchmark/manifests/format_robustness.json `
  --suite-name format-robustness-v1 `
  --reader-mode default `
  --retrieval-mode hybrid `
  --top-k 5
```

Outputs are written under `benchmark/artifacts/`.

When benchmarking `docqa_runtime` with an LLM that does not support
OpenAI-compatible tool calling, disable citation highlighting for the run:

```powershell
python -m benchmark run `
  --manifest benchmark/manifests/format_robustness.json `
  --suite-name docqa-document-deepseek `
  --engine docqa_runtime `
  --scope document `
  --llm-name Deepseek `
  --docqa-citation-mode off
```

`--docqa-citation-mode` accepts `highlight`, `inline`, or `off`. Use
`highlight`/`inline` only with models that support function/tool calling;
otherwise the citation sub-pipeline can fail while the overall benchmark still
finishes.

Each prediction row now includes:

- `evidence_metadata`: whether figure/image/formula/page visual context reached the generation path
- `claim_verification`: abstention and rewrite-skip behavior when the engine exposes it
- `presentation`: renderer or answer-format metadata when the engine exposes it
- `metrics`: text accuracy, retrieval grounding, false abstention, Markdown table, LaTeX, and guardrail scores

## FinanceBench

Normalize the official open-source release:

```powershell
python -m benchmark normalize-financebench `
  --source-dir D:\datasets\financebench `
  --output benchmark/manifests/financebench.json
```

## SlideVQA

This converter expects:

- a JSON annotation file
- a local document root that contains matching deck files by stem

```powershell
python -m benchmark normalize-slidevqa `
  --annotations D:\datasets\slidevqa\test.json `
  --documents-root D:\datasets\slidevqa\documents `
  --output benchmark/manifests/slidevqa.json
```

## Notes

- The benchmark now tracks visual and formula evidence metadata, but the score depends on the active reader/indexing pipeline surfacing those fields. If an engine cannot expose image/formula context, `evidence_metadata` makes that gap visible instead of hiding it inside answer text.
- `MP-DocVQA / DUDE / QASPER` can plug in by converting their raw data into the same manifest shape.
- The runner caches document parsing and indexing per document inside one run, so repeated questions on the same file are benchmarked as query-time work instead of repeated ingestion.
