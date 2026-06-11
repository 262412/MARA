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
- table, figure, formula, and slide hit rates for modality-aware routes
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
    },
    {
      "route_id": "mara_fast",
      "engine": "docqa_runtime",
      "scope": "document",
      "reasoning": "mara",
      "agent_mode": "fast"
    },
    {
      "route_id": "mara_thorough",
      "engine": "docqa_runtime",
      "scope": "document",
      "reasoning": "mara",
      "agent_mode": "thorough"
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

Use `direct_paste_document` as the "user pasted all available text" baseline. The DocQA routes should beat it on questions that require citations, page scope, figure/formula evidence, or multi-document retrieval. `mara_fast` and `mara_thorough` run the same runtime through the MARA reasoning mode for agentic ablations. `oracle_page` is an upper-bound diagnostic route: it answers from the gold page context and helps separate retrieval failures from generation or formatting failures.

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
- `agent_trace`: MARA planning, retrieval, verification, and final-decision events when the engine exposes them
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

## Thesis Route Templates

Route templates for the local-first thesis benchmark live under
`benchmark/manifests/templates/`:

- `mara_all_routes.local.json`: direct, text, page-image VLM, element, graph,
  hybrid, controller-auto, and CRAG-guarded routes.
- `mara_text_only.json`: text-focused ablations for FinanceBench, QASPER, ALCE,
  and RAGTruth style runs.
- `mara_multimodal.json`: text, page-image, element, hybrid, and controller
  routes for SlideVQA, MMDocRAG, and ViDoRe-style runs.

Copy one of these templates into a dataset manifest, then replace `documents`
and `examples` with the converter output or your curated manifest rows. The
local route templates use Qwen/BGE/ColQwen/Qwen-VL names as benchmark metadata;
actual runtime availability is still checked by the configured DocQA visual
backend health path.

## Dataset Converters

Additional converters target the thesis-scale benchmark datasets:

```powershell
python -m benchmark normalize-qasper `
  --source ~/scratch/datasets/MARA/qasper/raw/qasper-dev-v0.3.json `
  --output ~/scratch/outputs/MARA/manifests/qasper-dev.json

python -m benchmark normalize-mmdocrag `
  --source ~/scratch/datasets/MARA/mmdocrag/dev_20.jsonl `
  --documents-root ~/scratch/datasets/MARA/mmdocrag `
  --output ~/scratch/outputs/MARA/manifests/mmdocrag-dev20.json

python -m benchmark normalize-vidore `
  --source ~/scratch/datasets/MARA/vidore/docvqa_test_subsampled `
  --documents-root ~/scratch/datasets/MARA/vidore/docvqa_test_subsampled `
  --output ~/scratch/outputs/MARA/manifests/vidore-docvqa.json

python -m benchmark normalize-ragtruth `
  --source-info ~/scratch/datasets/MARA/ragtruth/dataset/source_info.jsonl `
  --responses ~/scratch/datasets/MARA/ragtruth/dataset/response.jsonl `
  --output ~/scratch/outputs/MARA/manifests/ragtruth.json

python -m benchmark normalize-alce `
  --source ~/data/datasets/MARA/alce/data/asqa_eval_gtr_top100.json `
  --output ~/scratch/outputs/MARA/manifests/alce-asqa.json
```

Converters write derived manifests and any materialized text documents to the
chosen output location. Keep those outputs under `~/scratch/outputs/MARA` or
another non-repository working area.

## Sampling And Sharding

Use sampling controls for smoke, small ablation, and sharded thesis runs:

```powershell
python -m benchmark run `
  --manifest ~/scratch/outputs/MARA/manifests/qasper-dev.json `
  --suite-name qasper-small-ablation `
  --route all `
  --limit 50 `
  --sample-seed 2026
```

For distributed runs, `--sample-seed` shuffles once, then
`--shard-index/--num-shards` selects a deterministic shard, then `--limit`
caps that shard:

```powershell
python -m benchmark run `
  --manifest ~/scratch/outputs/MARA/manifests/mmdocrag-dev20.json `
  --suite-name mmdocrag-shard-0 `
  --route all `
  --sample-seed 2026 `
  --shard-index 0 `
  --num-shards 4 `
  --limit 75
```

Reports include `route_metrics.csv`, route-level Markdown tables, backend
metadata, skipped routes, and evaluator status when route-matrix results are
available.

## Notes

- The benchmark now tracks visual and formula evidence metadata, but the score depends on the active reader/indexing pipeline surfacing those fields. If an engine cannot expose image/formula context, `evidence_metadata` makes that gap visible instead of hiding it inside answer text.
- `MP-DocVQA / DUDE / QASPER` can plug in by converting their raw data into the same manifest shape.
- The runner caches document parsing and indexing per document inside one run, so repeated questions on the same file are benchmarked as query-time work instead of repeated ingestion.
