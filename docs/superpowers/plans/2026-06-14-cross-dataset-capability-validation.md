# Cross-Dataset Capability Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate MARA retrieval, evidence, citation, verifier, and controller behavior across FinanceBench, QASPER, RAGTruth, ALCE, and later multimodal datasets without putting FinanceBench-specific logic in the generic runtime path.

**Architecture:** Move benchmark behavior to capability-driven profiles and normalized evidence records. Dataset names are allowed for manifest import, fixture selection, and reporting labels; route policy, retrieval diagnostics, citation scoring, verifier cleanup, and controller behavior must branch on data shape and capabilities, not on `financebench`.

**Tech Stack:** Python 3.10, existing `benchmark` package, MARA DocQA runtime under `libs/ktem`, JSON v2 manifests, pytest, `scripts/check_codebase_hygiene.py`, pre-commit.

---

## Non-Negotiable Direction

This plan intentionally reverses the narrow FinanceBench-tuning direction.

Allowed:

- FinanceBench-specific code only in FinanceBench import/normalization modules, FinanceBench fixtures, and FinanceBench tests.
- Dataset family labels in reports and artifact metadata.
- Optional domain-specific verifier plugins only when explicitly configured by a user-facing route field and tested as opt-in behavior.

Not allowed:

- Generic retrieval, evidence, citation, verifier, scorer, controller, or route-selection logic that checks `dataset_name == "financebench"` or imports `benchmark.financebench_*`.
- Benchmark success criteria that optimize FinanceBench page/citation metrics by weakening QASPER, RAGTruth, ALCE, or future multimodal behavior.
- Refreshing `scripts/codebase_hygiene_baseline.json` to make gates pass.
- Writing indexes, datasets, logs, caches, model files, or benchmark outputs inside the Git repository.

## Public Surface

Affected surfaces:

- Benchmark CLI behavior for `python -m benchmark run` and `apply-route-template`.
- Manifest JSON metadata and route JSON fields.
- Prediction JSONL keys: `gold_evidence`, `predicted_sources`, `predicted_pages`, `retrieved_hits`, `diagnostics`, `verify_decision`, `controller_decision`.
- Summary/report keys for retrieval, citation, verifier, and controller diagnostics.
- DocQA runtime behavior visible to benchmark runs: cleaned final answer, evidence bundle, verifier decision, route gating.
- Controller route policy for text-only and multimodal profiles.

Unaffected surfaces unless a task explicitly says otherwise:

- Public `MARA` / `MARA-cli` command names and options.
- DB schema and persisted app session shape.
- Gradio event chains.

## Storage Preflight Before Any Execution

Run before `uv`, tests, model calls, dataset sync, DocQA indexing, or Slurm:

```bash
cd ~/scratch/projects/MARA
ls -ld .venv
readlink -f .venv
readlink -f .venv/bin/python
df -h .venv ktem_app_data
printf 'UV_CACHE_DIR=%s\n' "$UV_CACHE_DIR"
printf 'UV_PYTHON_INSTALL_DIR=%s\n' "$UV_PYTHON_INSTALL_DIR"
printf 'PRE_COMMIT_HOME=%s\n' "$PRE_COMMIT_HOME"
printf 'HF_HOME=%s\n' "$HF_HOME"
printf 'TIKTOKEN_CACHE_DIR=%s\n' "$TIKTOKEN_CACHE_DIR"
printf 'CODEX_HOME=%s\n' "$CODEX_HOME"
printf 'KH_APP_DATA_DIR=%s\n' "$KH_APP_DATA_DIR"
lfs quota -h -u tbczhang /mnt/fastscratch
lfs quota -h -u tbczhang /mnt/scratch
quota -s
test ! -e data
test ! -e datasets
test ! -e outputs
```

Expected:

- Repository is `/mnt/scratch/users/tbczhang/projects/MARA`.
- `.venv` resolves to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Runtime/cache paths point to fastscratch, except `PRE_COMMIT_HOME` under scratch.
- fastscratch, scratch, and data are below soft quota.
- Repo root has no `data`, `datasets`, or `outputs`.

## Current Execution Posture

This plan is the main Plan(5) recovery path after the benchmark work started
drifting toward FinanceBench-specific fixes. Treat existing worktree changes as
draft implementation until the gates in Task 13 and the cross-dataset sample
runs in Tasks 11-12 prove them.

Execution rule:

1. Implement or repair generic benchmark/runtime behavior first.
2. Run focused unit tests for the capability touched.
3. Run the 1-sample readiness matrix across FinanceBench, QASPER, RAGTruth,
   and ALCE.
4. Analyze failures by generic taxonomy.
5. Only then run the 10-sample regression matrix.

Do not advance to a larger benchmark because one dataset improves. Advance only
when all four text datasets have no execution errors, no unintended visual
payload path, cleaned verifier/scorer input, and route diagnostics that explain
the remaining score.

## Cross-Dataset Failure Taxonomy

Use these failure classes when deciding the next fix:

| Failure class               | Meaning                                                                    | Generic fix direction                                                            |
| --------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `execution_error`           | Runtime, backend, context, or planner path failed before retrieval/scoring | Fix config propagation, backend selection, context cap, or runtime request shape |
| `no_retrieved_hits`         | Retriever returned no usable hits                                          | Fix index path, retriever query construction, or document selection              |
| `wrong_source`              | Hits exist, but none match the expected source/document                    | Fix source identity metadata, document routing, or query expansion               |
| `missing_locator_metadata`  | Hits lack page/span/source locator fields needed by the dataset shape      | Fix parser/index metadata projection generically                                 |
| `wrong_locator`             | Source is right but page/locator is wrong                                  | Fix locator alignment and retriever ranking, not dataset-specific scoring        |
| `gold_span_missing`         | Source/page may be right, but retrieved text does not contain support      | Fix chunking, retrieval depth, reranking, or span normalization                  |
| `citation_miss`             | Evidence exists but predicted citation cannot be matched                   | Fix citation normalization or source-level citation matching                     |
| `verifier_over_abstention`  | Verifier rejects a supported final answer                                  | Fix final-answer extraction or generic support criteria                          |
| `controller_route_mismatch` | Controller chose a route outside the data-shape capability                 | Fix route policy or controller metadata, not dataset score logic                 |

FinanceBench page misses, QASPER span misses, RAGTruth unsupported-label errors,
and ALCE citation misses must all map into this shared taxonomy.

## File Responsibility Map

- `benchmark/dataset_profiles.py`: capability profiles and route allowances by data shape.
- `benchmark/evidence_adapters.py`: normalized gold evidence records from source/page/span/citation/hallucination/multimodal inputs.
- `benchmark/page_alignment.py`: generic locator/page alignment, not FinanceBench-only page parsing.
- `benchmark/metrics.py`: citation/page/span metric primitives.
- `benchmark/scoring.py`: prediction-level score assembly using cleaned final answer and normalized evidence.
- `benchmark/diagnostics.py`: retrieval, evidence, citation, verifier, and controller failure classifications.
- `benchmark/manifest.py`: attach profile metadata while preserving manifest loading semantics.
- `benchmark/manifest_templates.py`: route-template composition by data shape.
- `benchmark/reports.py` and `benchmark/summary.py`: capability-level reporting tables.
- `benchmark/tests/test_no_finance_specialization_boundaries.py`: guardrail tests that prevent generic runtime/scoring/controller modules from importing FinanceBench adapters.
- `benchmark/tests/test_dataset_profiles.py`: dataset profile coverage for FinanceBench, QASPER, RAGTruth, ALCE, and multimodal dataset families.
- `benchmark/tests/test_evidence_adapters.py`: normalized evidence shape coverage.
- `benchmark/tests/test_page_alignment.py`: locator/page alignment coverage.
- `benchmark/tests/test_scoring.py`: citation and cleaned-answer scoring coverage.
- `benchmark/tests/test_runner_diagnostics.py`: failure taxonomy coverage.
- `libs/ktem/ktem/docqa/claim_filtering.py`: model-thought/final-answer cleanup.
- `libs/ktem/ktem/docqa/verification.py`: generic verifier path.
- `libs/ktem/ktem/docqa/domain_verifiers.py`: opt-in verifier registry only, not benchmark default behavior.
- `libs/ktem/ktem/reasoning/mara_route_retrieval.py`: route capability gating and visual payload separation.
- `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`: verifier cleanup regressions.
- `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`: controller route gating regressions.

---

### Task 1: Add Anti-Specialization Characterization Tests

**Files:**

- Create: `benchmark/tests/test_no_finance_specialization_boundaries.py`

- [ ] **Step 1: Write failing or characterization tests**

Create tests that define the allowed FinanceBench boundary:

```python
from __future__ import annotations

import ast
from pathlib import Path


GENERIC_RUNTIME_MODULES = (
    "benchmark/diagnostics.py",
    "benchmark/metrics.py",
    "benchmark/scoring.py",
    "benchmark/runner.py",
    "benchmark/manifest.py",
    "benchmark/manifest_templates.py",
    "benchmark/page_alignment.py",
    "libs/ktem/ktem/docqa/verification.py",
    "libs/ktem/ktem/reasoning/mara_route_retrieval.py",
)


def test_generic_runtime_layers_do_not_import_finance_specific_modules():
    repo = Path(__file__).resolve().parents[2]
    offenders = []
    for relative_path in GENERIC_RUNTIME_MODULES:
        tree = ast.parse((repo / relative_path).read_text(encoding="utf-8"))
        if _imports_finance_specific_module(tree):
            offenders.append(relative_path)

    assert offenders == []


def _imports_finance_specific_module(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_module_is_finance_specific(alias.name) for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if _module_is_finance_specific(node.module or ""):
                return True
    return False


def _module_is_finance_specific(module: str) -> bool:
    return any(
        part.startswith("finance")
        for part in str(module or "").strip(".").split(".")
    )
```

`benchmark/dataset_profiles.py` is intentionally excluded from this boundary test
because dataset family labels are allowed there. It must describe data shape; it
must not implement runtime/scoring/controller behavior.

- [ ] **Step 2: Run the test**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected now: failure if generic modules still mention FinanceBench or finance verifier imports.

- [ ] **Step 3: Move allowed FinanceBench compatibility to explicit adapter modules**

If the test fails, keep FinanceBench-specific parsing in files named for that dataset, such as:

- `benchmark/financebench_evidence.py`
- `benchmark/financebench_pages.py`
- FinanceBench-specific tests

Generic modules should consume the output of those adapters as normalized evidence records only.

- [ ] **Step 4: Re-run the boundary test**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected: pass.

---

### Task 2: Define Dataset Capabilities By Data Shape

**Files:**

- Modify: `benchmark/dataset_profiles.py`
- Modify: `benchmark/manifest.py`
- Test: `benchmark/tests/test_dataset_profiles.py`

- [ ] **Step 1: Add tests for capability fields**

Extend `benchmark/tests/test_dataset_profiles.py` so profiles expose capabilities instead of operational branches:

```python
def test_profiles_describe_capabilities_not_runtime_special_cases():
    finance = profile_for_manifest("financebench-main", examples=[])
    qasper = profile_for_manifest("qasper-dev", examples=[])
    ragtruth = profile_for_manifest("ragtruth", examples=[])
    alce = profile_for_manifest("alce-asqa", examples=[])

    assert finance.capabilities.page_evidence is True
    assert qasper.capabilities.span_evidence is True
    assert ragtruth.capabilities.hallucination_labels is True
    assert alce.capabilities.citation_quality is True
    assert finance.allowed_text_routes == ("doc_text", "hybrid", "graph_global")
    assert qasper.allowed_text_routes == ("doc_text", "hybrid", "graph_global")
    assert ragtruth.allowed_text_routes == ("doc_text", "hybrid", "graph_global")
    assert alce.allowed_text_routes == ("doc_text", "hybrid", "graph_global")
```

- [ ] **Step 2: Add profile shape fields**

Extend `DatasetCapabilities` with stable shape booleans or enums:

```python
@dataclass(frozen=True, slots=True)
class DatasetCapabilities:
    answer_correctness: bool
    page_evidence: bool
    span_evidence: bool
    citation_quality: bool
    hallucination_labels: bool
    multi_document: bool
    multimodal: bool
    source_level_citations: bool
    supports_abstention: bool
```

Do not add route behavior to the profile. The profile only describes data.

- [ ] **Step 3: Attach profile metadata without changing manifest compatibility**

In `benchmark/manifest.py`, keep the manifest JSON shape stable and attach derived metadata to `ManifestBundle.metadata["dataset_profile"]`.

- [ ] **Step 4: Run profile tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_dataset_profiles.py benchmark/tests/test_manifest.py -q
```

Expected: pass.

---

### Task 3: Normalize Gold Evidence Across Page, Span, Source, Citation, And Label Shapes

**Files:**

- Modify: `benchmark/evidence_adapters.py`
- Test: `benchmark/tests/test_evidence_adapters.py`

- [ ] **Step 1: Add cross-dataset evidence fixtures**

Add tests for these normalized records:

```python
def test_normalizes_qasper_span_evidence_without_pages():
    example = SimpleNamespace(
        gold_evidence=[{"document_id": "paper-1", "span": "neural IR improves recall"}],
        evidence_pages=[],
        evidence_sources=["paper-1"],
    )

    rows = normalize_gold_evidence(example)

    assert rows[0].document_id == "paper-1"
    assert rows[0].span_text == "neural IR improves recall"
    assert rows[0].page_label is None


def test_normalizes_ragtruth_hallucination_label():
    example = SimpleNamespace(
        gold_evidence=[{"source": "doc-7", "text": "gold support", "label": "unsupported"}],
        evidence_pages=[],
        evidence_sources=[],
    )

    rows = normalize_gold_evidence(example)

    assert rows[0].source == "doc-7"
    assert rows[0].span_text == "gold support"
    assert rows[0].support_label == "unsupported"
```

- [ ] **Step 2: Keep FinanceBench legacy parsing outside generic scoring**

If FinanceBench source strings require compatibility parsing, keep that parsing in a named FinanceBench adapter and call it only during manifest normalization. The normalized output must look like any other `NormalizedEvidence`.

- [ ] **Step 3: Add generic locator extraction**

Support common locator patterns across datasets:

- `page`, `page_label`, `page_index`
- `p. 12`, `page 12`, `Page: 12`
- `source#page=12`
- `document.pdf:12`

The parser must not check for FinanceBench names.

- [ ] **Step 4: Run evidence adapter tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_evidence_adapters.py -q
```

Expected: pass.

---

### Task 4: Audit And Repair Runtime Index Metadata Generically

**Files:**

- Create: `benchmark/index_metadata.py`
- Test: `benchmark/tests/test_index_metadata.py`
- Modify only if needed: `benchmark/docqa_runtime_sources.py`

- [ ] **Step 1: Add an index metadata contract**

Create tests asserting each retrieved text hit can expose generic fields when available:

```python
def test_text_hit_metadata_has_source_identity_and_optional_locator():
    hit = normalize_retrieved_hit(
        {
            "text": "The method improves recall.",
            "metadata": {"source_id": "paper-1", "page_label": "3"},
        }
    )

    assert hit["source_id"] == "paper-1"
    assert hit["page_label"] == "3"
    assert hit["text"] == "The method improves recall."
```

- [ ] **Step 2: Implement `normalize_retrieved_hit`**

The function should map common metadata names into:

- `source_id`
- `document_id`
- `page_label`
- `page_index`
- `element_id`
- `modality`
- `text`

- [ ] **Step 3: Ensure runtime sources use the normalized metadata**

If `benchmark/docqa_runtime_sources.py` emits source references, use the generic normalized fields. For text-only datasets without pages, emit source-level citations such as `paper-1#source` only when source identity is present.

- [ ] **Step 4: Run runtime source tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_docqa_runtime_engine_sources.py benchmark/tests/test_index_metadata.py -q
```

Expected: pass.

---

### Task 5: Make Retrieval Diagnostics Capability-Aware

**Files:**

- Modify: `benchmark/diagnostics.py`
- Test: `benchmark/tests/test_runner_diagnostics.py`

- [ ] **Step 1: Add diagnostics tests for each data shape**

Use prediction dictionaries to cover:

- FinanceBench-like page-grounded question with wrong page.
- QASPER-like source/span question with right source and missing span.
- RAGTruth-like hallucination label with no retrieved support.
- ALCE-like citation question with source-level citation and retrieved span.

Expected failure types:

- `no_retrieved_hits`
- `wrong_source`
- `missing_locator_metadata`
- `wrong_locator`
- `gold_span_missing`
- `citation_miss`
- `none`

- [ ] **Step 2: Implement diagnostics from capability inputs**

`prediction_diagnostics()` should decide which checks apply from the evidence shape:

- If no gold pages exist, do not report `wrong_page`.
- If gold spans exist, check span presence in retrieved hits and evidence bundle.
- If citation quality is expected, separate source hit from citation match.
- If hallucination labels exist, classify verifier/guardrail behavior separately from retrieval.

- [ ] **Step 3: Run diagnostics tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_runner_diagnostics.py benchmark/tests/test_reports_diagnostics.py -q
```

Expected: pass.

---

### Task 6: Score Citations By Exact Citation, Source-Level Citation, And Retrieved Span

**Files:**

- Modify: `benchmark/metrics.py`
- Modify: `benchmark/scoring.py`
- Test: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Add source/span citation regression tests**

Add tests where:

- exact citation IDs match and score is 1.0.
- source-level citation matches only if the retrieved text contains the gold span.
- source-level citation does not match if the span is absent.
- page citations are evaluated only when gold pages exist.

- [ ] **Step 2: Implement generic matching order**

Citation matching should use this order:

1. Exact citation ID match.
2. Same source/document plus locator match when locators exist.
3. Same source/document plus gold span found in retrieved evidence.

Do not add FinanceBench citation parsing here. Inputs should already be normalized.

- [ ] **Step 3: Run scoring tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_scoring.py -q
```

Expected: pass.

---

### Task 7: Verify Only The Final Answer, Not Model Thinking

**Files:**

- Modify: `libs/ktem/ktem/docqa/claim_filtering.py`
- Modify: `libs/ktem/ktem/docqa/verification.py`
- Test: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`

- [ ] **Step 1: Add cleaner tests**

Cover these answer shapes:

```text
<think>reasoning</think>
Final Answer: revenue was 10.2 million.
```

```text
analysis: reason through evidence
answer: the paper proposes a retrieval reranker.
```

```text
The answer is supported. Not enough evidence was considered during reasoning.
Final Answer: supported claim.
```

Expected: verifier and scorer see only final answer content.

- [ ] **Step 2: Keep verifier generic by default**

The default verifier should use generic claim/evidence overlap and generic numeric support. Domain-specific verifier plugins may exist only behind explicit route config, not as benchmark default.

- [ ] **Step 3: Run verifier regression tests**

Run:

```bash
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_docqa_verification_regressions.py -q
```

Expected: pass.

---

### Task 8: Gate Controller Routes By Modality And Capability

**Files:**

- Modify: `benchmark/controller_fields.py`
- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Test: `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`
- Test: `benchmark/tests/test_manifest_templates.py`

- [ ] **Step 1: Add text-only route policy tests**

For FinanceBench, QASPER, RAGTruth, and ALCE text profiles, controller auto should allow:

```python
["doc_text", "hybrid", "graph_global"]
```

It should not pass image payloads, visual retriever backends, or page-image metadata unless the manifest route explicitly enables multimodal capability.

- [ ] **Step 2: Add multimodal route policy tests**

For multimodal profiles, controller auto may allow:

```python
["doc_text", "hybrid", "doc_page_image", "doc_element", "graph_global"]
```

- [ ] **Step 3: Implement route gating**

The controller should read route/config capability fields, not dataset names. `hybrid` can combine text and structured routes; it must not send image payloads to a text LLM unless visual generation is explicitly configured.

- [ ] **Step 4: Run route tests**

Run:

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_manifest_templates.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  -q
```

Expected: pass.

---

### Task 9: Generate Cross-Dataset Text Manifests From Shape-Based Templates

**Files:**

- Modify: `benchmark/manifests/templates/mara_text_only.json`
- Modify: `benchmark/manifests/templates/mara_multimodal.json`
- Modify: `benchmark/manifest_templates.py`
- Test: `benchmark/tests/test_manifest_adapter_boundaries.py`

- [ ] **Step 1: Add template boundary tests**

Text-only templates must not contain these keys:

- `visual_retriever_backend`
- `visual_generator_backend`
- `visual_backend_type`
- page-image payload config

Multimodal templates may contain visual fields, but only in visual routes.

- [ ] **Step 2: Regenerate Plan 5 text manifests into scratch outputs**

Write generated manifests under:

```text
~/scratch/outputs/MARA/manifests/plan5/
```

Do not write generated manifests into the Git repository unless they are small curated templates.

- [ ] **Step 3: Inspect generated manifests**

Run a small JSON inspection script or `python -m json.tool` to verify route IDs and visual fields.

Expected text route IDs:

```text
direct_answer
text_rag
hybrid_rag
controller_auto
crag_guarded
```

Expected controller allowed routes for text-only datasets:

```text
doc_text, hybrid, graph_global
```

---

### Task 10: Add Cross-Dataset Capability Reports

**Files:**

- Modify: `benchmark/summary.py`
- Modify: `benchmark/reports.py`
- Test: `benchmark/tests/test_reports_diagnostics.py`

- [ ] **Step 1: Add report tests**

Reports should include tables for:

- Dataset capabilities.
- Retrieval failure counts.
- Citation failure counts.
- Verifier status counts.
- Controller selected route versus recommended route.

- [ ] **Step 2: Implement reporting from diagnostics**

Reports should make it obvious whether a failure is:

- actual retrieval miss,
- missing metadata,
- citation formatting mismatch,
- verifier over-abstention,
- controller route mismatch,
- unsupported expected behavior for the dataset shape.

- [ ] **Step 3: Run report tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_reports_diagnostics.py -q
```

Expected: pass.

---

### Task 11: Run 1-Sample Readiness Across FinanceBench, QASPER, RAGTruth, And ALCE

**Files:**

- No source edits expected.
- Outputs go under `~/scratch/outputs/MARA/artifacts`.

- [ ] **Step 1: Run one example per dataset route**

Use the generated scratch manifests and run the four datasets explicitly:

```bash
uv run --python 3.10 python -m benchmark run \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/financebench/financebench.text-main.routes.json \
  --suite-name plan5-financebench-1sample-readiness \
  --route all \
  --limit 1 \
  --max-context-length 2000 \
  --docqa-citation-mode inline \
  --reasoning mara \
  --output-dir ~/scratch/outputs/MARA/artifacts

uv run --python 3.10 python -m benchmark run \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/qasper/qasper-dev.text-main.routes.json \
  --suite-name plan5-qasper-1sample-readiness \
  --route all \
  --limit 1 \
  --max-context-length 2000 \
  --docqa-citation-mode inline \
  --reasoning mara \
  --output-dir ~/scratch/outputs/MARA/artifacts

uv run --python 3.10 python -m benchmark run \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/ragtruth/ragtruth.guardrail.routes.json \
  --suite-name plan5-ragtruth-1sample-readiness \
  --route all \
  --limit 1 \
  --max-context-length 2000 \
  --docqa-citation-mode inline \
  --reasoning mara \
  --output-dir ~/scratch/outputs/MARA/artifacts

uv run --python 3.10 python -m benchmark run \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/alce/alce-asqa-gtr.citation.routes.json \
  --suite-name plan5-alce-1sample-readiness \
  --route all \
  --limit 1 \
  --max-context-length 2000 \
  --docqa-citation-mode inline \
  --reasoning mara \
  --output-dir ~/scratch/outputs/MARA/artifacts
```

- [ ] **Step 2: Inspect summaries**

Expected readiness criteria:

- All text routes execute without visual payload errors.
- No `raw_retriever_zero` on every route for the same dataset.
- Diagnostics distinguish `wrong_source`, `wrong_locator`, and `gold_span_missing`.
- Verifier decisions are based on cleaned final answers.
- Controller route selections stay inside profile allowed routes.

---

### Task 12: Run 10-Sample Regression Matrix

**Files:**

- No source edits expected.
- Outputs go under `~/scratch/outputs/MARA/artifacts` and Slurm logs under `~/scratch/outputs/MARA/slurm` or `~/scratch/outputs/MARA/logs`.

- [ ] **Step 1: Submit small Slurm jobs**

Use the best idle GPU available; L40S is acceptable fallback. Jobs must read
datasets from `~/scratch/datasets/MARA` and write outputs to
`~/scratch/outputs/MARA`.

If running interactively before converting to Slurm, use this exact matrix:

```bash
for item in \
  "financebench ~/scratch/outputs/MARA/manifests/plan5/financebench/financebench.text-main.routes.json" \
  "qasper ~/scratch/outputs/MARA/manifests/plan5/qasper/qasper-dev.text-main.routes.json" \
  "ragtruth ~/scratch/outputs/MARA/manifests/plan5/ragtruth/ragtruth.guardrail.routes.json" \
  "alce ~/scratch/outputs/MARA/manifests/plan5/alce/alce-asqa-gtr.citation.routes.json"
do
  set -- $item
  dataset="$1"
  manifest="$(eval echo "$2")"
  uv run --python 3.10 python -m benchmark run \
    --manifest "$manifest" \
    --suite-name "plan5-${dataset}-10sample-$(date +%Y%m%d-%H%M%S)" \
    --route all \
    --output-dir ~/scratch/outputs/MARA/artifacts \
    --cache-mode warm \
    --max-context-length 2000 \
    --docqa-citation-mode inline \
    --reasoning mara \
    --artifact-detail compact \
    --limit 10 \
    --sample-seed 20260614
done
```

Expected:

```text
Benchmark complete. Outputs written to /users/tbczhang/scratch/outputs/MARA/artifacts/...
```

- [ ] **Step 2: Compare against 1-sample readiness**

For each dataset, record:

- retrieval hit rates by source/page/span,
- citation recall/precision,
- verifier unsupported/abstain counts,
- controller route-match counts,
- error counts,
- latency and cache stats.

Use this inspection command after the runs complete:

```bash
uv run --python 3.10 python - <<'PY'
import json
from pathlib import Path

root = Path("~/scratch/outputs/MARA/artifacts").expanduser()
for summary_path in sorted(root.glob("*/summary.json"))[-12:]:
    summary = json.loads(summary_path.read_text())
    print(summary_path.parent.name)
    print(" dataset:", summary.get("dataset_name"))
    print(" routes:", [row.get("route_id") for row in summary.get("route_metrics", [])])
    print(" diagnostics:", summary.get("diagnostic_counts", {}))
    print(" skipped:", summary.get("skipped_routes", []))
PY
```

- [ ] **Step 3: Decide next fixes by failure taxonomy**

Only fix generic causes:

- retrieval metadata missing,
- poor source/span recall,
- citation normalization mismatch,
- answer cleaning failure,
- verifier over-abstention,
- controller route mismatch.

Do not fix low FinanceBench score by adding FinanceBench-only scorer/controller/verifier branches.

---

### Task 13: Run Gates Before Claiming Ready

**Files:**

- All changed files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_index_metadata.py \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  benchmark/tests/test_manifest_templates.py \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run hygiene**

Run:

```bash
uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-files>
```

Expected:

```text
No codebase hygiene ratchet violations.
```

- [ ] **Step 3: Run pre-commit**

Run:

```bash
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

Expected: all hooks pass.

- [ ] **Step 4: Run final storage check**

Run the storage preflight again and confirm no repo-root `data`, `datasets`, or `outputs` appeared.

---

## Acceptance Criteria

- Generic benchmark/runtime layers do not import FinanceBench adapter modules or check FinanceBench names for behavior.
- FinanceBench, QASPER, RAGTruth, and ALCE each have a dataset profile and normalized evidence test.
- Text-only manifests do not configure visual payloads or visual backends.
- Citation metrics distinguish exact citation match, source-level support, and missing retrieved span.
- Verifier/scorer use cleaned final answer text and ignore model thought/analysis sections.
- Controller auto route policy is capability-based:
  - text-only: `doc_text`, `hybrid`, `graph_global`
  - multimodal: `doc_text`, `hybrid`, `doc_page_image`, `doc_element`, `graph_global`
- Reports explain whether failures come from retrieval, metadata, citation, verifier, or controller.
- 1-sample readiness runs complete for all four datasets before any larger benchmark.
- 10-sample regression results are analyzed by generic failure taxonomy, not by FinanceBench score alone.

## Residual Risks To Track

- Existing FinanceBench compatibility modules may remain necessary for legacy source strings; keep them isolated and document them as dataset import adapters.
- Official external evaluators for QASPER, RAGTruth, and ALCE may not match internal proxy metrics exactly. Reports must label proxy metrics clearly.
- Page labels from PDFs can differ from parser page indices. Treat this as a locator-alignment problem across all page-grounded datasets, not a FinanceBench-only correction.
- Small local Qwen context length can still limit answer quality. Do not compensate by weakening verifier or scorer logic.
