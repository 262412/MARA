# Cross-Dataset Capability Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate retrieval, evidence, citation, verifier, and controller behavior across FinanceBench, QASPER, RAGTruth, ALCE, and later multimodal datasets without narrowing the generic MARA runtime to FinanceBench.

**Architecture:** Treat each benchmark as a dataset capability profile plus normalized evidence/citation records. Dataset-specific code is allowed only in importer, adapter, fixture, or explicitly opted-in domain verifier boundaries; retrieval, source projection, citation scoring, default verification, and controller routing must branch on generic data-shape capabilities, not dataset names.

**Tech Stack:** Python 3.10, MARA `benchmark` package, MARA DocQA runtime under `libs/ktem`, JSON v2 manifests, pytest, `scripts/check_codebase_hygiene.py`, pre-commit, Slurm outputs under `~/scratch/outputs/MARA`.

---

## Reset Rule

This plan replaces score-chasing fixes that make the system narrower. A change is acceptable only if it fits one of these categories:

- `generic-capability`: improves source/page/span/layout/multimodal evidence behavior for more than one dataset family.
- `dataset-adapter`: normalizes a dataset-specific raw shape into the common manifest/evidence shape.
- `domain-opt-in`: applies a domain verifier or domain tolerance only when explicitly configured by manifest/profile.
- `diagnostic-only`: improves reports, labels, or failure taxonomy without changing runtime behavior.

Reject or isolate changes that add FinanceBench behavior to generic runtime paths.

Forbidden in generic modules:

- `if dataset_name == "financebench"` style behavior branches.
- Imports from `benchmark.financebench_*` or `ktem.docqa.finance_verification`.
- Default verifier/scorer assumptions that answers are financial, numeric, page-labeled, or table-derived.
- Mandatory page-label requirements for source-level datasets such as QASPER, RAGTruth, and ALCE.
- Passing image bytes, base64 payloads, or rendered image content into text-only LLM prompts.

Allowed FinanceBench-specific code:

- `benchmark/financebench_evidence.py`
- `benchmark/financebench_pages.py`
- `benchmark/manifest_legacy_adapters.py`
- FinanceBench fixtures and tests.
- `libs/ktem/ktem/docqa/finance_verification.py` only through an explicit `verification_domain="finance"` or equivalent route/profile opt-in.

## Public Surface

Affected public surfaces:

- Benchmark manifest metadata: `dataset_profile`, `capabilities`, `allowed_routes`, evidence fields.
- Prediction JSONL keys for retrieved hits, citations, verifier output, controller metadata, and diagnostics.
- `summary.json`, `route_metrics.csv`, and report diagnostic fields.
- Benchmark route templates and controller allowed-route policy.
- DocQA benchmark runtime evidence projection.

Unaffected public surfaces:

- `MARA` and `MARA-cli` command names.
- Top-level CLI option names unless a task explicitly adds a tested option.
- Gradio event order.
- App DB schema.
- Persisted interactive session shape.

## Shared Dataset Capability Model

Use capability flags rather than dataset-specific runtime branches:

| Dataset family    | Main shape                                                                | Required capability checks                                                                      |
| ----------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| FinanceBench      | multi-document financial filings, page evidence, numeric/text answers     | page locator optional-to-required by profile, source identity, span support, answer correctness |
| QASPER            | scientific paper QA, paragraph/span evidence, paper-level source identity | source identity, span support, answer correctness, citation quality proxy                       |
| RAGTruth          | hallucination labels and unsupported claims                               | source/span support, support label, abstention correctness, unsupported claim rate              |
| ALCE              | attribution/citation quality, source-level citations                      | source-level citation precision/recall, attributable claim support, answer correctness proxy    |
| Future multimodal | page image, layout element, text chunks, visual evidence                  | modality-aware route gating, no image payload leakage into text prompts                         |

Controller auto is governed by capabilities. The default text/document route set is:

```python
("doc_text", "hybrid", "doc_page_image", "doc_element", "graph_global")
```

`crag_guarded` may remain a benchmark route or guardrail wrapper, but controller route selection should not be made Finance-specific to enable it.

## File Responsibility Map

- `benchmark/dataset_profiles.py`: capability profiles and route allowlists.
- `benchmark/evidence_adapters.py`: normalized evidence records from generic page/source/span/citation/support-label inputs.
- `benchmark/manifest_legacy_adapters.py`: legacy FinanceBench compatibility bridge only.
- `benchmark/page_alignment.py`: generic page/locator alignment for any page-grounded dataset.
- `benchmark/citation_metrics.py`: citation matching by source, page, locator, and span.
- `benchmark/scoring.py`: answer, citation, support, abstention, and hallucination metrics over normalized records.
- `benchmark/diagnostics.py`: shared failure taxonomy.
- `benchmark/reports.py`: diagnostic summaries and proxy metric labeling.
- `benchmark/manifest_templates.py`: route templates from capabilities, not dataset names.
- `benchmark/docqa_runtime_sources.py`: runtime hit/source capture with safe text-only payloads.
- `benchmark/docqa_evidence_projection.py`: benchmark evidence projection from DocQA bundles.
- `benchmark/runner.py`: run orchestration and diagnostics aggregation.
- `libs/ktem/ktem/docqa/evidence_text.py`: final-answer extraction and thought cleanup.
- `libs/ktem/ktem/docqa/verification.py`: default generic verifier.
- `libs/ktem/ktem/docqa/domain_verifiers.py`: explicit opt-in domain verifier registry.
- `libs/ktem/ktem/reasoning/mara_route_retrieval.py`: route retrieval and modality-safe evidence handoff.
- `libs/ktem/ktem/reasoning/mara_controller.py`: controller route policy and trace.

## Required Preflight

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

Expected:

- Repository resolves to `/mnt/scratch/users/tbczhang/projects/MARA`.
- `.venv` resolves to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Caches and runtime data point to fastscratch, except `PRE_COMMIT_HOME` under scratch.
- fastscratch, scratch, and data quotas are below soft limits.
- Repository root has no `data`, `datasets`, or `outputs`.

---

### Task 0: Freeze And Audit Current Drift

**Files:**

- Modify: `benchmark/tests/test_no_finance_specialization_boundaries.py`
- Create: `~/scratch/outputs/MARA/reports/cross_dataset_capability_drift_audit_<timestamp>.md`

- [ ] **Step 1: Snapshot current worktree**

```bash
git status --short
```

Expected: preserve all existing user and agent changes; do not revert unrelated files.

- [ ] **Step 2: Run the specialization boundary test**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected: PASS. If it fails, the failing path is treated as the first fix.

- [ ] **Step 3: Ensure generic module coverage includes every runtime layer**

`GENERIC_RUNTIME_MODULES` in `benchmark/tests/test_no_finance_specialization_boundaries.py` must include at least:

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

- [ ] **Step 4: Write the drift audit report**

Create the report outside the repo with exactly these headings:

```markdown
# Cross-Dataset Capability Drift Audit

## Generic Capability Changes

## Dataset Adapter Changes

## Domain Opt-In Changes

## Diagnostic-Only Changes

## Reject Or Isolate Before Benchmarking
```

Expected: every changed benchmark/runtime file is classified before implementation continues.

- [ ] **Step 5: Commit the boundary/audit plan update**

```bash
git add benchmark/tests/test_no_finance_specialization_boundaries.py docs/superpowers/plans/2026-06-15-cross-dataset-capability-reset.md
git commit -m "test: lock cross-dataset benchmark boundaries"
```

Skip the commit only if the user wants changes left uncommitted.

### Task 1: Make Dataset Profiles Express Data Shape

**Files:**

- Modify: `benchmark/dataset_profiles.py`
- Modify: `benchmark/tests/test_dataset_profiles.py`
- Modify: `benchmark/manifest.py`
- Modify: `benchmark/manifest_templates.py`

- [ ] **Step 1: Write profile contract tests**

Add or keep tests with this shape:

```python
def test_profiles_describe_capabilities_not_runtime_special_cases():
    finance = profile_for_dataset("financebench-main")
    qasper = profile_for_dataset("qasper-dev")
    ragtruth = profile_for_dataset("ragtruth")
    alce = profile_for_dataset("alce-asqa")

    assert finance.capabilities.page_evidence is True
    assert qasper.capabilities.span_evidence is True
    assert ragtruth.capabilities.hallucination_labels is True
    assert alce.capabilities.source_level_citations is True
    assert finance.allowed_routes == qasper.allowed_routes
    assert finance.allowed_routes == ragtruth.allowed_routes
    assert finance.allowed_routes == alce.allowed_routes
```

- [ ] **Step 2: Run the profile tests red or green**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_dataset_profiles.py -q
```

Expected: PASS if current profiles already match; otherwise fail only on capability semantics.

- [ ] **Step 3: Implement capability fields without behavior branches**

`DatasetCapabilities` must represent data shape:

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

Expected: generic runtime modules consume these flags and do not special-case dataset names.

- [ ] **Step 4: Attach profiles during manifest loading**

`load_manifest()` must expose:

```python
bundle.metadata["dataset_profile"]
bundle.metadata["capabilities"]
bundle.metadata["allowed_routes"]
```

Expected: downstream runner, reports, and templates can read capability metadata from manifest bundles.

- [ ] **Step 5: Verify profile/template behavior**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_manifest_templates.py \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  -q
```

Expected: all pass.

### Task 2: Normalize Evidence Once, Then Score Generically

**Files:**

- Modify: `benchmark/evidence_adapters.py`
- Modify: `benchmark/manifest_legacy_adapters.py`
- Modify: `benchmark/tests/test_evidence_adapters.py`
- Modify: `benchmark/tests/test_manifest_adapter_boundaries.py`

- [ ] **Step 1: Write cross-dataset evidence fixtures**

Use one evidence type for all families:

```python
def test_normalizes_cross_dataset_evidence_shapes():
    cases = [
        ({"document_id": "filing", "page": 58, "span": "cash flow"}, "page"),
        ({"document_id": "paper", "span": "method improves recall"}, "source"),
        ({"document_id": "rag", "span": "unsupported claim", "label": "unsupported"}, "source"),
        ({"document_id": "alce-doc", "citation": "alce-doc#source", "span": "attributable"}, "source"),
    ]

    for raw, locator_kind in cases:
        evidence = normalize_gold_evidence_record(raw)
        assert evidence.locator_kind == locator_kind
        assert evidence.source_id == raw["document_id"]
```

- [ ] **Step 2: Keep Finance legacy parsing outside generic evidence**

Generic evidence code may parse common locator strings, but must not import FinanceBench helpers. Legacy FinanceBench parsing lives in `benchmark/manifest_legacy_adapters.py`:

```python
from benchmark.manifest_legacy_adapters import legacy_evidence_from_source
```

Expected: `benchmark/evidence_adapters.py` has no `financebench` import or string branch.

- [ ] **Step 3: Implement normalized evidence fields**

`NormalizedEvidence` must expose these generic fields:

```python
@dataclass(frozen=True, slots=True)
class NormalizedEvidence:
    document_id: str | None
    page_label: str | None
    page_index: int | None
    source: str | None
    span_text: str | None
    element_id: str | None
    modality: str | None
    support_label: str | None
```

Expected: page evidence, source evidence, span evidence, element evidence, and hallucination labels can be represented without dataset-specific runtime logic.

- [ ] **Step 4: Verify evidence boundary**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  -q
```

Expected: all pass.

### Task 3: Fix Retrieval And Runtime Source Projection By Data Shape

**Files:**

- Modify: `benchmark/docqa_runtime_sources.py`
- Modify: `benchmark/docqa_evidence_projection.py`
- Modify: `benchmark/tests/test_docqa_runtime_engine_sources.py`
- Modify: `benchmark/tests/test_runtime_mara_capture.py`
- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Modify: `libs/ktem/ktem_tests/test_mara_retrieval_quality.py`

- [ ] **Step 1: Write source projection tests for text-only and multimodal-safe paths**

Add assertions equivalent to:

```python
def test_runtime_sources_keep_text_hits_and_strip_image_payloads():
    rows = project_runtime_sources(
        [
            {
                "document_id": "doc",
                "page_label": "3",
                "text": "Relevant support span.",
                "image": "data:image/png;base64,AAAA",
            }
        ]
    )

    assert rows[0]["document_id"] == "doc"
    assert rows[0]["page_label"] == "3"
    assert rows[0]["text"] == "Relevant support span."
    assert "data:image" not in str(rows[0])
    assert "base64" not in str(rows[0]).lower()
```

- [ ] **Step 2: Ensure selected-file and source identity survive retrieval**

Runtime hits must preserve:

```python
{
    "document_id": "...",
    "source_id": "...",
    "page_label": "...",
    "page_index": 0,
    "text": "...",
    "source_backrefs": ["doc#page:1"],
    "modality": "text",
}
```

Expected: FinanceBench page recall, QASPER source/span recall, RAGTruth support labels, and ALCE source citations can be evaluated from the same hit shape.

- [ ] **Step 3: Classify empty retrieval generically**

Do not turn empty retrieval into Finance-specific abstention. Diagnostics should distinguish:

```python
"no_retrieved_hits"
"wrong_source"
"missing_locator_metadata"
"wrong_locator"
"gold_span_missing"
```

- [ ] **Step 4: Verify retrieval projection**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  benchmark/tests/test_runtime_mara_capture.py \
  libs/ktem/ktem_tests/test_mara_retrieval_quality.py \
  -q
```

Expected: all pass, and no image payload appears in text runtime source rows.

### Task 4: Align Locators Without Making Page Labels Universal

**Files:**

- Modify: `benchmark/page_alignment.py`
- Modify: `benchmark/citation_metrics.py`
- Modify: `benchmark/scoring.py`
- Modify: `benchmark/tests/test_page_alignment.py`
- Modify: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Write page-grounded and source-grounded tests**

```python
def test_page_alignment_is_only_required_for_page_grounded_profiles():
    page_metrics = score_prediction(_prediction_with_gold_page_and_correct_hit())
    source_metrics = score_prediction(_prediction_with_source_span_and_no_page())

    assert page_metrics["citation_recall_page"] == 1.0
    assert source_metrics["citation_recall_source"] == 1.0
    assert "citation_recall_page" in page_metrics
    assert source_metrics["gold_page_required"] == 0.0
```

- [ ] **Step 2: Match citation quality in this order**

```text
1. exact source + exact page or element locator, when the profile requires locator evidence
2. exact source + retrieved gold span
3. source-level citation, when the profile supports source-level citations
4. support-label match, for hallucination/guardrail datasets
```

Expected: FinanceBench can improve page exact recall without penalizing ALCE/RAGTruth for lacking page labels.

- [ ] **Step 3: Keep page alignment generic**

`benchmark/page_alignment.py` may normalize page labels such as `p. 7`, `#page:7`, and parser index offsets. It must not check for `financebench`.

- [ ] **Step 4: Verify scoring and locator behavior**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_citation_metrics.py \
  benchmark/tests/test_scoring.py \
  -q
```

Expected: all pass.

### Task 5: Keep Default Verification Generic, Make Domain Verification Explicit

**Files:**

- Modify: `libs/ktem/ktem/docqa/evidence_text.py`
- Modify: `libs/ktem/ktem/docqa/verification.py`
- Modify: `libs/ktem/ktem/docqa/domain_verifiers.py`
- Modify: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`
- Modify: `benchmark/scoring.py`
- Modify: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Lock final-answer cleanup**

Tests must cover tagged and untagged reasoning:

```python
def test_clean_answer_text_uses_final_answer_not_reasoning():
    answer = "<think>wrong scratch</think>\n\nFinal answer: The method improves recall."

    assert clean_answer_text(answer) == "The method improves recall."
    assert answer_claims(answer) == ["The method improves recall."]
```

- [ ] **Step 2: Lock default verifier against Finance adapters**

```python
def test_default_verifier_does_not_apply_finance_numeric_adapter():
    payload = build_controller_outputs(
        DocQARequest(prompt="Question", verification_mode="strict"),
        [],
        _quick_ratio_evidence_metadata(),
        answer="3M's quick ratio was 1.20.",
    )

    assert payload["verify_decision"]["status"] != "unsupported_by_finance_adapter"
```

- [ ] **Step 3: Keep Finance verifier opt-in only**

Finance numeric logic is allowed only with:

```python
DocQARequest(
    prompt="...",
    verification_mode="strict",
    verification_domain="finance",
)
```

Expected: QASPER, RAGTruth, and ALCE never get Finance numeric claim filtering by default.

- [ ] **Step 4: Verify cleanup, verifier, and scorer**

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  benchmark/tests/test_scoring.py \
  -q
```

Expected: all pass, and verifier/scorer-visible fields do not contain `<think>` or rendered thought blocks.

### Task 6: Route Controller By Capability, Not Dataset Name

**Files:**

- Modify: `benchmark/manifest_templates.py`
- Modify: `benchmark/tests/test_manifest_templates.py`
- Modify: `libs/ktem/ktem/reasoning/mara_controller.py`
- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Modify: `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`
- Modify: `libs/ktem/ktem_tests/test_mara_controller_routes.py`

- [ ] **Step 1: Write route allowlist tests**

```python
def test_text_profiles_share_controller_allowed_routes():
    expected = ("doc_text", "hybrid", "doc_page_image", "doc_element", "graph_global")

    for dataset in ("financebench", "qasper", "ragtruth", "alce"):
        assert profile_for_dataset(dataset).allowed_routes == expected
```

- [ ] **Step 2: Keep visual routes capability-gated**

Controller may list visual-capable routes in the allowlist, but route execution must skip or downgrade only when the backend lacks required modality support. The skip reason must be explicit:

```text
route_unavailable:missing_visual_backend
route_unavailable:missing_element_index
route_unavailable:profile_text_only
```

- [ ] **Step 3: Preserve controller trace**

Every `controller_auto` prediction must expose:

```python
{
    "selected_route": "...",
    "allowed_routes": [...],
    "route_decision_reason": "...",
    "skipped_routes": [...],
}
```

Expected: benchmark reports can tell whether a failure is retrieval, route gating, or controller choice.

- [ ] **Step 4: Verify controller routing**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_manifest_templates.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  libs/ktem/ktem_tests/test_mara_controller_routes.py \
  -q
```

Expected: all pass.

### Task 7: Report Generic Failure Taxonomy Across All Datasets

**Files:**

- Modify: `benchmark/diagnostics.py`
- Modify: `benchmark/reports.py`
- Modify: `benchmark/summary.py`
- Modify: `benchmark/tests/test_runner_diagnostics.py`
- Modify: `benchmark/tests/test_reports_diagnostics.py`

- [ ] **Step 1: Write taxonomy coverage tests**

```python
def test_diagnostics_use_generic_failure_classes():
    prediction = {
        "retrieved_hits": [],
        "predicted_sources": [],
        "gold_evidence": [{"document_id": "paper", "span": "support"}],
    }

    assert classify_prediction_failure(prediction) == "no_retrieved_hits"
```

- [ ] **Step 2: Add report columns**

Route metrics and reports must include:

```text
no_retrieved_hits
wrong_source
missing_locator_metadata
wrong_locator
gold_span_missing
citation_miss
verifier_over_abstention
verifier_under_abstention
controller_route_mismatch
image_payload_leak
thought_leak
```

- [ ] **Step 3: Label proxy metrics**

Reports must state that QASPER/RAGTruth/ALCE metrics are internal proxy metrics unless official evaluator integration is active.

- [ ] **Step 4: Verify diagnostics reports**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  -q
```

Expected: all pass.

### Task 8: Run A Cross-Dataset Readiness Matrix Before Any Main Benchmark

**Files:**

- No repo code changes.
- Slurm scripts and outputs under `~/scratch/outputs/MARA`.

- [ ] **Step 1: Run 1-sample matrix**

Run one example each for FinanceBench, QASPER, RAGTruth, and ALCE with the current text/main/guardrail/citation manifests. Expected routes:

```text
doc_text
hybrid
controller_auto
crag_guarded
```

Expected artifact checks:

```text
summary.json exists
predictions.jsonl exists
route_metrics.csv exists
report.md exists
num_errors == 0
no text field contains <think>
no text field contains data:image or base64 payloads
every failure maps to the generic taxonomy
```

- [ ] **Step 2: Stop on generic failure leakage**

Do not proceed to 10-sample if any 1-sample artifact shows:

```text
image_payload_leak
thought_leak
FinanceBench branch in generic runtime
all routes empty retrieval for a dataset with valid indexed source files
controller route outside allowed_routes
```

- [ ] **Step 3: Run 10-sample matrix**

Run the same datasets sequentially or as Slurm dependencies:

```text
FinanceBench 10
QASPER 10
RAGTruth 10
ALCE 10
```

Expected: do not optimize for aggregate score yet. Use this run to classify failures by data shape.

- [ ] **Step 4: Write benchmark analysis**

Create:

```text
~/scratch/outputs/MARA/reports/cross_dataset_10sample_capability_analysis_<timestamp>.md
```

The report must include:

```markdown
## Capability Summary

## Retrieval Failures

## Evidence And Citation Failures

## Verifier And Abstention Failures

## Controller Route Failures

## Dataset Adapter Issues

## Generic Fixes To Implement Next

## Dataset-Specific Fixes Kept Out Of Runtime
```

### Task 9: Run Required Verification Gates

**Files:**

- All changed Python files.
- This plan file.

- [ ] **Step 1: Run focused tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  benchmark/tests/test_runtime_mara_capture.py \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_manifest_templates.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  libs/ktem/ktem_tests/test_mara_retrieval_quality.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run codebase hygiene on changed Python files**

```bash
uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>
```

Expected: `No codebase hygiene ratchet violations.`

- [ ] **Step 3: Run pre-commit on changed files**

```bash
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

Expected: all hooks pass. Do not refresh `scripts/codebase_hygiene_baseline.json`.

- [ ] **Step 4: Run final storage layout check**

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

- Generic runtime/scoring/controller modules do not import FinanceBench adapters or branch on FinanceBench identifiers.
- FinanceBench, QASPER, RAGTruth, and ALCE each have a dataset profile and normalized evidence coverage.
- Retrieval output preserves source/page/span metadata when available and does not leak image payloads into text-only prompts.
- Page alignment improves page-grounded datasets without making page labels mandatory for source-level datasets.
- Default verifier/scorer evaluate cleaned final answers, not chain-of-thought or rendered thought blocks.
- Finance numeric verification is opt-in only.
- Controller auto uses capability allowlists, not dataset-specific route policy.
- 1-sample and 10-sample cross-dataset results are analyzed by the generic failure taxonomy before any main benchmark.
- Any remaining FinanceBench-only behavior is isolated to FinanceBench adapter/importer/test boundaries and documented as such.

## Residual Risks

- Internal proxy metrics for QASPER, RAGTruth, and ALCE may not match official leaderboard metrics. Reports must label them as proxy metrics until official evaluator integration is added.
- PDF page labels can differ from parser page indices. Treat this as a generic locator-alignment problem, not FinanceBench correction logic.
- Some multimodal route checks may skip when local VLM or element indexes are unavailable. Skips are acceptable only when explicit and reported.
- Current benchmark sample sizes are diagnostic. Do not claim final system performance from 1-sample or 10-sample runs.

Plan complete and saved to `docs/superpowers/plans/2026-06-15-cross-dataset-capability-reset.md`.
