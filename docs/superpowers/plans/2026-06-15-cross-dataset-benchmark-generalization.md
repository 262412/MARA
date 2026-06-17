# Cross-Dataset Benchmark Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate and improve MARA retrieval, evidence, citation, verifier, and controller behavior across FinanceBench, QASPER, RAGTruth, and ALCE without adding FinanceBench-specific behavior to generic runtime paths.

**Architecture:** Represent every benchmark as a dataset profile plus normalized evidence records. Generic code branches on data-shape capabilities such as source, page, span, support label, citation, modality, and abstention support; dataset-specific logic stays in converters, legacy adapters, fixtures, or explicitly configured domain verifiers.

**Tech Stack:** Python 3.10, MARA `benchmark` package, DocQA runtime under `libs/ktem`, JSON v2 manifests, pytest, `scripts/check_codebase_hygiene.py`, pre-commit, Slurm outputs under `~/scratch/outputs/MARA`.

---

## Non-Negotiable Design Rule

Generic modules must not contain FinanceBench-specific branches, imports, prompts, scoring assumptions, verifier assumptions, or controller route policies. FinanceBench-specific code is allowed only in:

- `benchmark/financebench_evidence.py`
- `benchmark/financebench_pages.py`
- `benchmark/manifest_legacy_adapters.py`
- FinanceBench converter fixtures and tests
- an explicit opt-in verifier path such as `verification_domain="finance"`

The implementation must classify every change as one of:

- `generic-capability`: improves a common data-shape behavior for multiple dataset families.
- `dataset-adapter`: converts one dataset's raw format into the common benchmark shape.
- `domain-opt-in`: applies domain-specific verification only when requested by manifest/profile/request.
- `diagnostic-only`: improves labels, reports, or failure attribution without runtime behavior changes.

Reject or isolate any change that improves FinanceBench by making page labels, financial numerics, filing names, table-derived answers, or FinanceBench citations mandatory in generic code.

## Public Surface

Affected public surfaces:

- Benchmark manifest metadata: `dataset_profile`, `capabilities`, `allowed_routes`, evidence fields.
- Prediction JSONL keys: `retrieved_hits`, `gold_evidence`, `evidence_bundle`, `predicted_sources`, verifier output, controller trace, diagnostics.
- `summary.json`, `route_metrics.csv`, `report.md`, and diagnostic report sections.
- Benchmark route templates and controller allowed-route policy.
- DocQA benchmark runtime source projection.

Unaffected public surfaces:

- `MARA` and `MARA-cli` command names.
- Top-level CLI option names unless a task explicitly adds a tested option.
- Gradio event order.
- App DB schema.
- Persisted interactive session shape.

## Data Shape Matrix

| Dataset      | Primary shape                                               | Generic capabilities to verify                                                               | Dataset-specific boundary                                             |
| ------------ | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| FinanceBench | multi-document filings, page evidence, numeric/text answers | source identity, optional page locator, span recall, citation quality, answer correctness    | finance importers, legacy evidence adapter, optional finance verifier |
| QASPER       | paper QA, source/span evidence                              | source identity, span recall, source-level citation proxy, answer correctness                | QASPER converter only                                                 |
| RAGTruth     | hallucination and unsupported claim labels                  | support label, abstention correctness, unsupported claim rate, source/span support           | RAGTruth converter only                                               |
| ALCE         | attribution and citation quality                            | source-level citation recall/precision, attributable claim support, answer correctness proxy | ALCE converter only                                                   |

Controller default allowlist for benchmark-capable document routes:

```python
("doc_text", "hybrid", "doc_page_image", "doc_element", "graph_global")
```

Routes requiring unavailable modality support must skip with explicit route-unavailable diagnostics, not with dataset-specific filtering.

## File Responsibility Map

- `benchmark/dataset_profiles.py`: dataset family and data-shape capabilities.
- `benchmark/manifest.py`: attaches derived profile metadata to loaded manifests.
- `benchmark/manifest_templates.py`: applies route templates without dataset-name runtime policy.
- `benchmark/evidence_adapters.py`: converts raw evidence dictionaries to normalized evidence records.
- `benchmark/manifest_legacy_adapters.py`: isolates legacy FinanceBench evidence compatibility.
- `benchmark/docqa_runtime_sources.py`: canonical runtime hit/source projection and payload stripping.
- `benchmark/docqa_evidence_projection.py`: maps DocQA evidence bundles into benchmark evidence fields.
- `benchmark/page_alignment.py`: generic page/locator alignment.
- `benchmark/citation_metrics.py`: source/page/span/element citation matching.
- `benchmark/scoring.py`: capability-aware answer, citation, abstention, support, and hallucination metrics.
- `benchmark/diagnostics.py`: generic failure taxonomy and controller route diagnostics.
- `benchmark/reports.py`: user-facing report tables and proxy metric labels.
- `benchmark/runner.py`: orchestration and diagnostics aggregation.
- `libs/ktem/ktem/docqa/evidence_text.py`: final-answer extraction and thought cleanup.
- `libs/ktem/ktem/docqa/verification.py`: default generic verifier.
- `libs/ktem/ktem/docqa/domain_verifiers.py`: explicit opt-in domain verifier registry if needed.
- `libs/ktem/ktem/reasoning/mara_controller.py`: controller route policy and trace.
- `libs/ktem/ktem/reasoning/mara_route_retrieval.py`: route retrieval and modality-safe evidence handoff.

## Required Preflight Before Execution

Run before `uv`, tests, model calls, indexing, dataset sync, or Slurm:

```bash
cd ~/scratch/projects/MARA
pwd
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

Expected: repository is `/mnt/scratch/users/tbczhang/projects/MARA`, `.venv` resolves to `/mnt/fastscratch/users/tbczhang/envs/mara`, caches/runtime are outside the repo, quotas are below soft limits, and no repo-root `data`, `datasets`, or `outputs` directory exists.

---

### Task 1: Lock Generic Boundaries Before More Fixes

**Files:**

- Modify: `benchmark/tests/test_no_finance_specialization_boundaries.py`
- Create: `~/scratch/outputs/MARA/reports/cross_dataset_boundary_audit_<timestamp>.md`

- [ ] **Step 1: Snapshot current worktree**

```bash
git status --short
```

Expected: existing user changes are identified and preserved.

- [ ] **Step 2: Expand the generic-module boundary list**

Ensure `GENERIC_RUNTIME_MODULES` covers these runtime and reporting paths:

```python
GENERIC_RUNTIME_MODULES = (
    "benchmark/citation_metrics.py",
    "benchmark/diagnostics.py",
    "benchmark/docqa_evidence_projection.py",
    "benchmark/docqa_runtime_sources.py",
    "benchmark/engines.py",
    "benchmark/evidence_adapters.py",
    "benchmark/manifest.py",
    "benchmark/manifest_templates.py",
    "benchmark/metrics.py",
    "benchmark/page_alignment.py",
    "benchmark/reports.py",
    "benchmark/runner.py",
    "benchmark/scoring.py",
    "benchmark/summary.py",
    "libs/ktem/ktem/docqa/evidence_text.py",
    "libs/ktem/ktem/docqa/verification.py",
    "libs/ktem/ktem/reasoning/mara_controller.py",
    "libs/ktem/ktem/reasoning/mara_route_retrieval.py",
)
```

- [ ] **Step 3: Run the boundary test**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected: PASS. If it fails, fix or move the offending behavior into an allowed adapter/domain-opt-in boundary before continuing.

- [ ] **Step 4: Write a drift audit outside the repo**

Create `~/scratch/outputs/MARA/reports/cross_dataset_boundary_audit_<timestamp>.md` with these exact sections:

```markdown
# Cross-Dataset Boundary Audit

## Generic Capability Changes

## Dataset Adapter Changes

## Domain Opt-In Changes

## Diagnostic-Only Changes

## Changes To Reject Or Isolate
```

Expected: every changed benchmark/runtime file is classified before new implementation starts.

### Task 2: Make Dataset Profiles Express Data Shape

**Files:**

- Modify: `benchmark/dataset_profiles.py`
- Modify: `benchmark/manifest.py`
- Modify: `benchmark/tests/test_dataset_profiles.py`
- Modify: `benchmark/tests/test_manifest.py`

- [ ] **Step 1: Add profile tests for all four dataset families**

Add or keep tests equivalent to:

```python
def test_profiles_describe_data_shape_not_dataset_specific_runtime_policy():
    finance = profile_for_dataset("financebench-main")
    qasper = profile_for_dataset("qasper-dev")
    ragtruth = profile_for_dataset("ragtruth")
    alce = profile_for_dataset("alce-asqa")

    assert finance.capabilities.page_evidence is True
    assert finance.capabilities.source_level_citations is False
    assert qasper.capabilities.span_evidence is True
    assert qasper.capabilities.source_level_citations is True
    assert ragtruth.capabilities.hallucination_labels is True
    assert ragtruth.capabilities.supports_abstention is True
    assert alce.capabilities.citation_quality is True
    assert alce.capabilities.source_level_citations is True

    expected_routes = (
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    )
    assert finance.allowed_routes == expected_routes
    assert qasper.allowed_routes == expected_routes
    assert ragtruth.allowed_routes == expected_routes
    assert alce.allowed_routes == expected_routes
```

- [ ] **Step 2: Verify manifests attach profile metadata**

Add a manifest-loading test with one temporary QASPER-style manifest:

```python
def test_load_manifest_attaches_dataset_profile_and_capabilities(tmp_path):
    (tmp_path / "paper.txt").write_text("paper text", encoding="utf-8")
    manifest_path = tmp_path / "qasper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper-dev",
                "documents": [
                    {
                        "document_id": "paper",
                        "path": "paper.txt",
                        "format_type": "txt",
                    }
                ],
                "examples": [
                    {
                        "example_id": "q1",
                        "document_ids": ["paper"],
                        "question": "What does the paper show?",
                        "answers": ["It improves recall."],
                        "gold_evidence": [
                            {
                                "document_id": "paper",
                                "span": "improves recall",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.metadata["dataset_profile"].dataset_family == "qasper"
    assert bundle.metadata["capabilities"]["span_evidence"] is True
    assert bundle.metadata["allowed_routes"] == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]
```

- [ ] **Step 3: Implement or preserve capability metadata**

`DatasetCapabilities` must represent the common data shape:

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

Expected: downstream code reads capabilities from the manifest bundle instead of checking dataset names.

- [ ] **Step 4: Run profile and manifest tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_manifest.py \
  benchmark/tests/test_manifest_templates.py \
  -q
```

Expected: PASS.

### Task 3: Normalize Evidence Once, Then Reuse It Everywhere

**Files:**

- Modify: `benchmark/evidence_adapters.py`
- Modify: `benchmark/manifest_legacy_adapters.py`
- Modify: `benchmark/tests/test_evidence_adapters.py`
- Modify: `benchmark/tests/test_manifest_adapter_boundaries.py`

- [ ] **Step 1: Add cross-dataset evidence normalization tests**

Add test cases covering page, source/span, support label, and citation-target evidence:

```python
def test_normalizes_cross_dataset_evidence_shapes():
    cases = [
        (
            {"document_id": "filing", "page": 58, "span": "cash flow"},
            {"source_id": "filing", "page_label": "58", "locator_kind": "page"},
        ),
        (
            {"document_id": "paper", "span": "method improves recall"},
            {"source_id": "paper", "page_label": None, "locator_kind": "source"},
        ),
        (
            {"document_id": "rag", "span": "unsupported claim", "label": "unsupported"},
            {"source_id": "rag", "support_label": "unsupported"},
        ),
        (
            {"document_id": "alce-doc", "citation": "alce-doc#source", "span": "attributable"},
            {"source_id": "alce-doc", "locator_kind": "source"},
        ),
    ]

    for raw, expected in cases:
        evidence = normalize_gold_evidence_record(raw)
        for key, value in expected.items():
            assert getattr(evidence, key) == value
```

- [ ] **Step 2: Keep legacy Finance parsing out of generic evidence code**

`benchmark/evidence_adapters.py` may parse common locators such as `#page:7`, `p. 7`, and `document.pdf:7`. It must not import `benchmark.financebench_evidence`, `benchmark.financebench_pages`, or check for the string `financebench`.

- [ ] **Step 3: Ensure normalized evidence has one generic field set**

`NormalizedEvidence` must preserve:

```python
NormalizedEvidence(
    document_id=document_id,
    page_label=row_page,
    page_index=page_index,
    source=citation,
    span_text=span_text,
    element_id=element_id,
    modality=modality,
    support_label=support_label,
)
```

Expected: scoring, diagnostics, and reports can evaluate all four datasets from the same shape.

- [ ] **Step 4: Run evidence boundary tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  -q
```

Expected: PASS.

### Task 4: Fix Runtime Retrieval Projection As a Generic Source Contract

**Files:**

- Modify: `benchmark/docqa_runtime_sources.py`
- Modify: `benchmark/docqa_evidence_projection.py`
- Modify: `benchmark/tests/test_docqa_runtime_engine_sources.py`
- Modify: `benchmark/tests/test_runtime_mara_capture.py`
- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Modify: `libs/ktem/ktem_tests/test_mara_retrieval_quality.py`

- [ ] **Step 1: Add text-safe runtime source tests**

Add a test that proves retrieval hits preserve metadata and strip image payloads from text-only evidence:

```python
def test_runtime_sources_preserve_text_metadata_without_image_payloads():
    rows = canonicalize_docqa_hits(
        [
            {
                "document_id": "runtime-file-id",
                "source_id": "runtime-file-id",
                "source_name": "paper.pdf",
                "page_label": "3",
                "page_index": 2,
                "text": "Relevant support span.",
                "image": "data:image/png;base64,AAAA",
                "rendered_page_image": "data:image/png;base64,BBBB",
            }
        ],
        documents=[
            BenchmarkDocument(
                document_id="paper",
                path=Path("paper.pdf"),
                format_type="pdf",
                metadata={},
            )
        ],
        selected_file_ids=["runtime-file-id"],
    )

    assert rows[0]["document_id"] == "paper"
    assert rows[0]["source_id"] == "paper"
    assert rows[0]["page_label"] == "3"
    assert rows[0]["page_index"] == 2
    assert rows[0]["text"] == "Relevant support span."
    assert "data:image" not in json.dumps(rows[0]).lower()
    assert "base64" not in json.dumps(rows[0]).lower()
```

- [ ] **Step 2: Preserve canonical source identity**

Every benchmark runtime hit should expose these fields when available:

```python
{
    "document_id": "canonical-manifest-document-id",
    "source_id": "canonical-manifest-document-id",
    "runtime_source_id": "runtime-file-id",
    "source_name": "paper.pdf",
    "page_label": "3",
    "page_index": 2,
    "text": "Relevant support span.",
    "source_backrefs": ["canonical-manifest-document-id#page:3"],
    "modality": "text",
}
```

Expected: FinanceBench can evaluate page recall, QASPER/ALCE can evaluate source/span citation quality, and RAGTruth can evaluate support without separate retrieval paths.

- [ ] **Step 3: Classify empty retrieval as retrieval failure, not verifier failure**

Diagnostics must separate:

```text
no_retrieved_hits
wrong_source
missing_locator_metadata
wrong_locator
gold_span_missing
citation_miss
verifier_over_abstention
controller_route_mismatch
```

Expected: a verifier abstention after nonempty retrieval is not mislabeled as raw retrieval zero.

- [ ] **Step 4: Run retrieval projection tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  benchmark/tests/test_runtime_mara_capture.py \
  libs/ktem/ktem_tests/test_mara_retrieval_quality.py \
  -q
```

Expected: PASS and no image/base64 payload appears in text-source assertions.

### Task 5: Align Locators Without Requiring Page Labels Universally

**Files:**

- Modify: `benchmark/page_alignment.py`
- Modify: `benchmark/citation_metrics.py`
- Modify: `benchmark/scoring.py`
- Modify: `benchmark/tests/test_page_alignment.py`
- Modify: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Add page-grounded and source-grounded scoring tests**

Add tests with explicit predictions:

```python
def test_page_locator_metrics_apply_only_when_gold_has_pages():
    page_prediction = {
        "gold_answers": ["cash flow improved"],
        "predicted_answer": "cash flow improved",
        "predicted_pages": ["58"],
        "gold_pages": ["58"],
        "predicted_sources": ["filing#page:58"],
        "gold_sources": ["filing#page:58"],
        "gold_evidence": [
            {"document_id": "filing", "page": "58", "span": "cash flow improved"}
        ],
        "retrieved_hits": [
            {"document_id": "filing", "page_label": "58", "text": "cash flow improved"}
        ],
    }
    source_prediction = {
        "gold_answers": ["method improves recall"],
        "predicted_answer": "method improves recall",
        "predicted_pages": [],
        "gold_pages": [],
        "predicted_sources": ["paper#source"],
        "gold_sources": ["paper#source"],
        "gold_evidence": [
            {"document_id": "paper", "citation": "paper#source", "span": "method improves recall"}
        ],
        "retrieved_hits": [
            {"document_id": "paper", "text": "method improves recall"}
        ],
    }

    page_metrics = score_prediction(page_prediction)
    source_metrics = score_prediction(source_prediction)

    assert page_metrics["citation_recall_page"] == 1.0
    assert source_metrics["citation_recall_source"] == 1.0
    assert source_metrics["citation_recall_page"] is None
```

- [ ] **Step 2: Match citations by most specific available locator**

Implement citation matching in this order:

```text
1. exact source plus exact page or element, when gold evidence has that locator
2. exact source plus gold span, when gold evidence has span text
3. source-level citation, when no finer locator is required
4. support-label match for hallucination or guardrail examples
```

Expected: page-grounded examples benefit from better page alignment, while source-level datasets are not penalized for missing pages.

- [ ] **Step 3: Keep page alignment generic**

`benchmark/page_alignment.py` may normalize `7`, `p. 7`, `#page:7`, `page=7`, parser zero-based indices, and PDF labels. It must not contain `financebench`.

- [ ] **Step 4: Run locator and scoring tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_citation_metrics.py \
  -q
```

Expected: PASS.

### Task 6: Clean Thought Text Before Verifier And Scorer

**Files:**

- Modify: `libs/ktem/ktem/docqa/evidence_text.py`
- Modify: `libs/ktem/ktem/docqa/verification.py`
- Modify: `benchmark/scoring.py`
- Modify: `benchmark/tests/test_scoring.py`
- Modify: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`

- [ ] **Step 1: Add final-answer extraction tests**

Add tests covering tagged and untagged reasoning:

```python
def test_extract_final_answer_text_removes_tagged_reasoning():
    answer = "<think>wrong scratch</think>\n\nFinal answer: The method improves recall."

    assert extract_final_answer_text(answer) == "The method improves recall."


def test_scoring_uses_final_answer_not_reasoning():
    metrics = score_prediction(
        {
            "gold_answers": ["The method improves recall."],
            "predicted_answer": (
                "<think>The answer might be different.</think>\n"
                "Final answer: The method improves recall."
            ),
            "predicted_pages": [],
            "gold_pages": [],
            "predicted_sources": [],
            "gold_sources": [],
        }
    )

    assert metrics["f1"] == 1.0
```

- [ ] **Step 2: Ensure verifier receives cleaned answer text**

The default verifier should evaluate the final answer and claim text after thought cleanup. It must not inspect `<think>...</think>` blocks, model scratchpads, or rendered reasoning sections.

- [ ] **Step 3: Keep finance numeric verification opt-in**

Finance-specific numeric tolerance or ratio handling is allowed only when the request, route, or manifest explicitly sets a finance verification domain:

```python
DocQARequest(
    prompt="...",
    verification_mode="strict",
    verification_domain="finance",
)
```

Expected: QASPER, RAGTruth, and ALCE never pass through Finance numeric claim filtering by default.

- [ ] **Step 4: Run verifier and scorer tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_scoring.py \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  -q
```

Expected: PASS and tested verifier/scorer-visible text contains no `<think>`.

### Task 7: Route Controller By Capability And Trace Every Decision

**Files:**

- Modify: `benchmark/manifest_templates.py`
- Modify: `benchmark/tests/test_manifest_templates.py`
- Modify: `benchmark/diagnostics.py`
- Modify: `libs/ktem/ktem/reasoning/mara_controller.py`
- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Modify: `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`
- Modify: `libs/ktem/ktem_tests/test_mara_controller_routes.py`

- [ ] **Step 1: Add route allowlist tests**

```python
def test_cross_dataset_text_profiles_share_controller_allowed_routes():
    expected = (
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    )

    for dataset_name in ("financebench", "qasper", "ragtruth", "alce"):
        assert profile_for_dataset(dataset_name).allowed_routes == expected
```

- [ ] **Step 2: Gate unavailable routes by capability and backend state**

Use explicit skip reasons:

```text
route_unavailable:missing_visual_backend
route_unavailable:missing_element_index
route_unavailable:profile_text_only
route_unavailable:backend_error
```

Expected: a text-only profile can list visual-capable routes for future controller choice, while route execution reports why those routes did not run.

- [ ] **Step 3: Preserve controller trace in predictions**

Every `controller_auto` prediction must expose:

```python
{
    "selected_route": "doc_text",
    "allowed_routes": [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ],
    "route_decision_reason": "selected text route from source/span evidence request",
    "skipped_routes": [],
}
```

Expected: diagnostics can distinguish bad route selection from bad retrieval and bad verification.

- [ ] **Step 4: Run controller tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_manifest_templates.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  libs/ktem/ktem_tests/test_mara_controller_routes.py \
  -q
```

Expected: PASS.

### Task 8: Report A Generic Failure Taxonomy Across Datasets

**Files:**

- Modify: `benchmark/diagnostics.py`
- Modify: `benchmark/reports.py`
- Modify: `benchmark/summary.py`
- Modify: `benchmark/tests/test_runner_diagnostics.py`
- Modify: `benchmark/tests/test_reports_diagnostics.py`

- [ ] **Step 1: Add prediction-level failure taxonomy tests**

```python
def test_prediction_diagnostics_classifies_empty_retrieval_generically():
    diagnostics = prediction_diagnostics(
        {
            "route": "doc_text",
            "retrieved_hits": [],
            "predicted_sources": [],
            "gold_evidence": [{"document_id": "paper", "span": "support"}],
            "predicted_answer": "Final answer: Not enough evidence.",
            "gold_answers": ["support"],
        }
    )

    assert diagnostics["retrieval_failure_type"] == "no_retrieved_hits"
    assert diagnostics["failure_class"] == "no_retrieved_hits"
```

- [ ] **Step 2: Add report table coverage**

`report.md` and `summary.json` must surface at least:

```text
failure_class
retrieval_failure_type
citation_failure_type
controller_route_match
recommended_routes
```

Expected: reports show whether low score comes from retrieval, metadata, citation, verifier, controller, or payload leaks.

- [ ] **Step 3: Label non-official metrics as proxy metrics**

Reports for QASPER, RAGTruth, and ALCE must state when scores are internal proxy metrics instead of official leaderboard evaluators.

- [ ] **Step 4: Run diagnostics report tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  -q
```

Expected: PASS.

### Task 9: Build Cross-Dataset Readiness Matrix Before Main Benchmarks

**Files:**

- No repo code changes.
- Create reports under `~/scratch/outputs/MARA/reports`.
- Create Slurm logs and artifacts under `~/scratch/outputs/MARA`.

- [ ] **Step 1: Run 1-sample readiness matrix**

Run one example for each:

```text
FinanceBench: doc_text, hybrid, controller_auto, crag_guarded
QASPER: doc_text, hybrid, controller_auto, crag_guarded
RAGTruth: doc_text, hybrid, controller_auto, crag_guarded
ALCE: doc_text, hybrid, controller_auto, crag_guarded
```

Expected artifact checks:

```text
summary.json exists
predictions.jsonl exists
route_metrics.csv exists
report.md exists
num_errors == 0
every prediction has diagnostics.failure_class
no verifier/scorer/report-visible text contains <think>
no text prompt/evidence/report field contains data:image or base64 payloads
controller_auto selected route is in allowed_routes
```

- [ ] **Step 2: Stop on generic leakage**

Do not proceed to 10-sample if any 1-sample artifact shows:

```text
image_payload_leak
thought_leak
FinanceBench branch in generic runtime
all routes empty retrieval for a dataset with valid indexed source files
controller route outside allowed_routes
missing diagnostics.failure_class
```

- [ ] **Step 3: Run 10-sample diagnostic matrix**

Run:

```text
FinanceBench 10 examples
QASPER 10 examples
RAGTruth 10 examples
ALCE 10 examples
```

Expected: do not tune for aggregate score yet. Use this run to classify failure modes by data shape.

- [ ] **Step 4: Write analysis report**

Create `~/scratch/outputs/MARA/reports/cross_dataset_10sample_capability_analysis_<timestamp>.md` with:

```markdown
# Cross-Dataset 10-Sample Capability Analysis

## Capability Summary

## Retrieval Failures

## Evidence And Citation Failures

## Verifier And Abstention Failures

## Controller Route Failures

## Dataset Adapter Issues

## Generic Fixes To Implement Next

## Dataset-Specific Fixes Kept Out Of Runtime

## Stop Or Proceed Decision
```

Expected: next fixes are chosen from generic failure classes, not from FinanceBench score deltas alone.

### Task 10: Add Official Evaluator Boundaries Without Blocking Generic Diagnostics

**Files:**

- Modify: `benchmark/research_evaluators.py`
- Modify: `benchmark/tests/test_research_evaluators.py`
- Modify: `benchmark/reports.py`
- Modify: `benchmark/tests/test_research_evaluator_reports.py`

- [ ] **Step 1: Lock proxy-vs-official labeling**

Add a test equivalent to:

```python
def test_report_labels_proxy_metrics_when_official_evaluator_is_absent():
    summary = {
        "dataset_name": "qasper-dev",
        "evaluation_mode": "proxy",
        "avg_f1": 0.25,
        "avg_citation_recall": 0.5,
    }

    lines = _summary_markdown_lines(summary, "qasper-smoke")

    assert any("proxy" in line.lower() for line in lines)
```

- [ ] **Step 2: Keep official evaluator code optional and dataset-scoped**

Official evaluator adapters may know about QASPER/RAGTruth/ALCE metric names, but they must return normalized metric payloads into generic reports:

```python
{
    "evaluation_mode": "official",
    "official_metrics": {
        "dataset": "qasper",
        "metric_name": 0.0,
    },
}
```

Expected: missing official evaluator dependencies do not block generic readiness diagnostics.

- [ ] **Step 3: Run evaluator tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_research_evaluators.py \
  benchmark/tests/test_research_evaluator_reports.py \
  -q
```

Expected: PASS.

### Task 11: Run Required Verification Gates

**Files:**

- All changed Python files.
- This plan file.

- [ ] **Step 1: Run focused benchmark tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  benchmark/tests/test_runtime_mara_capture.py \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_manifest.py \
  benchmark/tests/test_manifest_templates.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  benchmark/tests/test_research_evaluators.py \
  benchmark/tests/test_research_evaluator_reports.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run focused DocQA/controller tests when those files change**

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  libs/ktem/ktem_tests/test_mara_controller_routes.py \
  libs/ktem/ktem_tests/test_mara_retrieval_quality.py \
  -q
```

Expected: PASS when the listed test files exist or are introduced by the task.

- [ ] **Step 3: Run codebase hygiene on changed Python files**

```bash
uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>
```

Expected: `No codebase hygiene ratchet violations.`

- [ ] **Step 4: Run pre-commit on changed files**

```bash
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

Expected: all hooks pass. Do not refresh `scripts/codebase_hygiene_baseline.json`.

- [ ] **Step 5: Run final storage layout check**

```bash
readlink -f .venv
readlink -f .venv/bin/python
df -h .venv ktem_app_data
lfs quota -h -u tbczhang /mnt/fastscratch
lfs quota -h -u tbczhang /mnt/scratch
quota -s
test ! -e data
test ! -e datasets
test ! -e outputs
```

Expected: layout remains valid and quotas remain below soft limits.

## Final Acceptance Criteria

- Generic benchmark/runtime modules pass the no-Finance-specialization boundary test.
- FinanceBench, QASPER, RAGTruth, and ALCE each have a data-shape profile and normalized evidence coverage.
- Runtime retrieval output preserves source/page/span metadata when available.
- Text-only prompts, artifacts, verifier inputs, and scorer inputs do not contain image/base64 payloads.
- Verifier and scorer evaluate cleaned final answers, not `<think>` blocks or reasoning text.
- Page/locator alignment improves page-grounded datasets without making page labels mandatory for source-level datasets.
- Default verifier remains generic; finance verifier behavior is opt-in only.
- Controller auto uses capability allowlists and records selected route, allowed routes, skipped routes, and route decision reason.
- Reports separate retrieval, evidence, citation, verifier, controller, payload, and thought-leak failures.
- 1-sample and 10-sample cross-dataset matrices are used as readiness diagnostics before any main benchmark.
- QASPER, RAGTruth, and ALCE scores are labeled as proxy metrics unless official evaluator integration is explicitly active.

## Residual Risks

- Proxy metrics may not match official QASPER, RAGTruth, or ALCE leaderboard metrics.
- PDF page labels and parser page indices can diverge; this remains a generic locator-alignment issue.
- Some visual routes may skip until local multimodal backends or element indexes are available; skips are acceptable only when explicit.
- Ten-sample results are diagnostic and should not be treated as final system performance.
