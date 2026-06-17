# Cross-Dataset Generalization Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate and improve MARA retrieval, evidence, citation, verifier, and controller behavior across FinanceBench, QASPER, RAGTruth, and ALCE by modeling dataset shape and task capability, not by adding FinanceBench-specific generic runtime logic.

**Architecture:** Keep generic benchmark and DocQA runtime code capability-driven. Dataset-specific handling lives in converters, dataset profiles, legacy adapters, fixtures, or explicit `verification_domain` opt-in paths. Runtime decisions should branch on evidence shape such as source, page, span, support label, modality, citation target, and abstention expectation.

**Tech Stack:** Python 3.10, pytest, MARA `benchmark` package, DocQA runtime under `libs/ktem`, JSON manifest templates, Slurm outputs under `~/scratch/outputs/MARA`, hygiene gate via `scripts/check_codebase_hygiene.py`, pre-commit.

---

## Non-Negotiable Boundary

Generic code must not make FinanceBench the default mental model. The following are allowed only in explicit boundaries:

- FinanceBench import and legacy evidence parsing: `benchmark/financebench_evidence.py`, `benchmark/financebench_pages.py`, `benchmark/manifest_legacy_adapters.py`.
- Finance-specific verifier behavior: `verification_domain="finance"` or `libs/ktem/ktem/docqa/domain_verifiers.py`.
- Finance-specific fixtures and regression tests.

The following are forbidden in generic runtime paths:

- requiring page labels for datasets whose evidence is source-level or span-level;
- requiring financial statement fields for generic retrieval adequacy;
- boosting table/statement terms unless a route explicitly opts into finance domain;
- treating FinanceBench citation/page exactness as the global citation metric;
- hiding benchmark failures by adding dataset-name branches in controller, scorer, or verifier.

Every implementation change must be classified as one of:

- `generic-capability`: improves behavior across multiple dataset shapes;
- `dataset-adapter`: converts one dataset format into the shared shape;
- `domain-opt-in`: domain logic only under explicit manifest/request config;
- `diagnostic-only`: report or failure attribution, no runtime behavior change.

## Public Surface

Affected public surfaces:

- benchmark manifest metadata: `dataset_profile`, `capabilities`, `allowed_routes`, route `verification_domain`;
- prediction records: `retrieved_hits`, `gold_evidence`, `predicted_sources`, `evidence_bundle`, `claim_verification`, `diagnostics`;
- artifact files: `summary.json`, `route_metrics.csv`, `documents.json`, `report.md`;
- benchmark route templates and controller route allowlists.

Unaffected public surfaces unless a later task explicitly adds tests:

- `MARA` and `MARA-cli` command names and top-level CLI options;
- Gradio event chain order;
- DB schema;
- persisted interactive session shape.

## Required Storage Preflight

Run before `uv`, pytest, indexing, dataset sync, Slurm, model serving, or any command that can create many files:

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

Expected: repo is `~/scratch/projects/MARA`; `.venv` resolves to `/mnt/fastscratch/users/tbczhang/envs/mara`; caches and runtime are outside the repo; quotas are below soft limits; repo root has no `data`, `datasets`, or `outputs`.

## File Responsibility Map

- `benchmark/dataset_profiles.py`: dataset-family and data-shape capabilities.
- `benchmark/manifest.py`: attach profiles and route metadata to manifests.
- `benchmark/manifest_templates.py`: apply route templates without dataset-name runtime policy.
- `benchmark/evidence_adapters.py`: normalize raw gold evidence into source/page/span/element/support records.
- `benchmark/docqa_evidence_projection.py`: normalize DocQA runtime evidence into benchmark fields.
- `benchmark/docqa_runtime_sources.py`: strip unsafe payloads and project runtime sources.
- `benchmark/index_metadata.py`: preserve source/page/span metadata from runtime indexes.
- `benchmark/page_alignment.py`: generic page/locator alignment utilities.
- `benchmark/citation_metrics.py`: source/page/span/element citation metrics.
- `benchmark/scoring.py`: capability-aware scoring and final-answer cleanup before metrics.
- `benchmark/diagnostics.py`: generic failure taxonomy.
- `benchmark/reports.py`: capability-aware report rendering.
- `benchmark/runner.py`: prediction normalization and diagnostics aggregation.
- `libs/ktem/ktem/docqa/evidence_text.py`: strip thought text and extract final answer.
- `libs/ktem/ktem/docqa/verification.py`: generic answer/evidence verifier.
- `libs/ktem/ktem/docqa/domain_verifiers.py`: explicit domain verifier registry.
- `libs/ktem/ktem/docqa/retrieval_adequacy.py`: generic retrieval adequacy plus opt-in domains.
- `libs/ktem/ktem/docqa/hybrid_fusion.py`: generic evidence ranking plus opt-in domain boosts.
- `libs/ktem/ktem/docqa/controller.py`: route selection and evidence sufficiency.
- `libs/ktem/ktem/reasoning/mara_controller.py`: agentic controller route policy and trace.
- `libs/ktem/ktem/reasoning/mara_route_retrieval.py`: modality-safe route retrieval handoff.

---

### Task 1: Lock The Finance Boundary Before More Fixes

**Files:**

- Modify: `benchmark/tests/test_no_finance_specialization_boundaries.py`
- Modify: `benchmark/tests/test_manifest_adapter_boundaries.py`
- Optional output: `~/scratch/outputs/MARA/reports/cross_dataset_boundary_audit_<timestamp>.md`

- [ ] **Step 1: Write or extend the generic-module scan**

Use this test shape so generic modules can mention `finance` only through explicit domain keys or test-safe metadata:

```python
GENERIC_RUNTIME_MODULES = (
    "benchmark/citation_metrics.py",
    "benchmark/diagnostics.py",
    "benchmark/docqa_evidence_projection.py",
    "benchmark/docqa_runtime_sources.py",
    "benchmark/evidence_adapters.py",
    "benchmark/index_metadata.py",
    "benchmark/manifest_templates.py",
    "benchmark/metrics.py",
    "benchmark/page_alignment.py",
    "benchmark/reports.py",
    "benchmark/runner.py",
    "benchmark/scoring.py",
    "libs/ktem/ktem/docqa/evidence_text.py",
    "libs/ktem/ktem/docqa/verification.py",
    "libs/ktem/ktem/reasoning/mara_controller.py",
    "libs/ktem/ktem/reasoning/mara_route_retrieval.py",
)


def test_generic_runtime_modules_do_not_contain_financebench_policy():
    forbidden = ("FinanceBench", "financebench", "financial statement")
    allowed_phrases = ("verification_domain", "domain_verifier")
    for path in GENERIC_RUNTIME_MODULES:
        text = Path(path).read_text()
        for phrase in forbidden:
            assert phrase not in text or any(allowed in text for allowed in allowed_phrases)
```

- [ ] **Step 2: Add adapter-boundary coverage**

Add a manifest/template test that proves FinanceBench routes opt into finance domain and text/citation datasets do not:

```python
def test_only_financebench_template_sets_finance_verification_domain():
    finance = routes_for_template("mara_financebench_text")
    text = routes_for_template("mara_text_only")

    assert all(
        route.get("verification_domain") == "finance"
        for route in finance
        if route["route_id"] in {"doc_text", "hybrid", "controller_auto", "crag_guarded"}
    )
    assert not any(route.get("verification_domain") == "finance" for route in text)
```

- [ ] **Step 3: Run the boundary tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  -q
```

Expected: tests fail only if Finance-specific policy is still leaking into generic paths.

### Task 2: Make Dataset Profiles Capability-Complete

**Files:**

- Modify: `benchmark/dataset_profiles.py`
- Modify: `benchmark/manifest.py`
- Modify: `benchmark/tests/test_dataset_profiles.py`
- Modify: `benchmark/tests/test_manifest.py`

- [ ] **Step 1: Add profile tests for FinanceBench, QASPER, RAGTruth, and ALCE**

```python
def test_profiles_describe_dataset_shape_and_not_scoring_shortcuts():
    finance = profile_for_dataset("financebench-main")
    qasper = profile_for_dataset("qasper-dev")
    ragtruth = profile_for_dataset("ragtruth")
    alce = profile_for_dataset("alce-asqa")

    assert finance.capabilities.page_evidence is True
    assert finance.capabilities.span_evidence is True
    assert qasper.capabilities.source_level_citations is True
    assert qasper.capabilities.span_evidence is True
    assert ragtruth.capabilities.hallucination_labels is True
    assert ragtruth.capabilities.supports_abstention is True
    assert alce.capabilities.citation_quality is True
    assert alce.capabilities.source_level_citations is True

    assert finance.allowed_routes == qasper.allowed_routes
    assert qasper.allowed_routes == ragtruth.allowed_routes
    assert ragtruth.allowed_routes == alce.allowed_routes
```

- [ ] **Step 2: Ensure manifests carry profile metadata**

Add assertions that loaded bundles expose serializable capabilities:

```python
def test_load_manifest_attaches_dataset_profile_metadata(tmp_path):
    bundle = load_manifest(tmp_path / "qasper.json")

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

- [ ] **Step 3: Implement only missing profile fields**

If current profile fields are insufficient, add capability names that describe evidence shape, not dataset names:

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

- [ ] **Step 4: Run the profile and manifest tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_manifest.py \
  -q
```

Expected: profile decisions are data-shape decisions; no dataset-specific scorer policy is hidden in profile loading.

### Task 3: Normalize Evidence Across Source, Page, Span, Element, And Support

**Files:**

- Modify: `benchmark/evidence_adapters.py`
- Modify: `benchmark/docqa_evidence_projection.py`
- Modify: `benchmark/docqa_runtime_sources.py`
- Modify: `benchmark/index_metadata.py`
- Modify: `benchmark/tests/test_evidence_adapters.py`
- Modify: `benchmark/tests/test_index_metadata.py`
- Modify: `benchmark/tests/test_docqa_runtime_engine_sources.py`

- [ ] **Step 1: Add cross-dataset evidence normalization tests**

```python
def test_normalized_evidence_supports_source_page_span_element_and_support_label():
    row = {
        "document_id": "paper-1",
        "citation": "paper-1#page:7",
        "page": "7",
        "page_index": 6,
        "span": "The study used retrieval augmented generation.",
        "element_id": "table-2",
        "modality": "table",
        "support_label": "supported",
    }

    evidence = normalize_gold_evidence_record(row)

    assert evidence.source_id == "paper-1"
    assert evidence.page_label == "7"
    assert evidence.parser_page_index == 6
    assert evidence.text_span == "The study used retrieval augmented generation."
    assert evidence.element_id == "table-2"
    assert evidence.modality == "table"
    assert evidence.support_label == "supported"
```

- [ ] **Step 2: Add payload-stripping regression coverage**

```python
def test_runtime_sources_strip_image_payloads_but_keep_locator_metadata():
    hit = {
        "text": "Revenue appears on page 5.",
        "metadata": {
            "source": "report.pdf",
            "page_label": "5",
            "image_origin": "data:image/png;base64,AAAA",
        },
    }

    projected = retrieved_hits_from_docqa_evidence([hit])

    assert projected[0]["source_id"] == "report.pdf"
    assert projected[0]["page_label"] == "5"
    assert "data:image" not in repr(projected[0])
    assert "base64" not in repr(projected[0])
```

- [ ] **Step 3: Implement missing projections generically**

Runtime evidence records should preserve these fields when present:

```python
KEEP_METADATA_KEYS = {
    "source",
    "source_id",
    "document_id",
    "page",
    "page_label",
    "page_index",
    "span",
    "element_id",
    "modality",
    "support_label",
    "retriever_score",
    "reranker_score",
}

DROP_PAYLOAD_KEYS = {
    "image_origin",
    "rendered_page_image",
    "image_base64",
    "page_image_base64",
}
```

- [ ] **Step 4: Run evidence projection tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_index_metadata.py \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  -q
```

Expected: all four evidence shapes can be represented without image payload leaks.

### Task 4: Make Retrieval Diagnostics Capability-Aware

**Files:**

- Modify: `benchmark/diagnostics.py`
- Modify: `benchmark/metrics.py`
- Modify: `benchmark/runner.py`
- Modify: `benchmark/tests/test_runner_diagnostics.py`
- Modify: `benchmark/tests/test_metrics.py`

- [ ] **Step 1: Add retrieval failure-class tests for each shape**

```python
def test_failure_class_uses_source_miss_for_source_level_dataset():
    prediction = prediction_with(
        capabilities={"source_level_citations": True, "page_evidence": False},
        gold_evidence=[{"document_id": "paper-1", "span": "RAG is used."}],
        retrieved_hits=[{"source_id": "paper-2", "text": "Other paper."}],
    )

    assert classify_failure(prediction) == "source_miss"


def test_failure_class_uses_wrong_locator_only_when_page_evidence_is_supported():
    prediction = prediction_with(
        capabilities={"source_level_citations": False, "page_evidence": True},
        gold_evidence=[{"document_id": "report", "page": 5}],
        retrieved_hits=[{"source_id": "report", "page_label": "9"}],
    )

    assert classify_failure(prediction) == "wrong_locator"
```

- [ ] **Step 2: Implement generic failure classes**

Use these names consistently in predictions, summaries, and reports:

```python
FAILURE_CLASSES = (
    "none",
    "no_retrieved_hits",
    "source_miss",
    "wrong_locator",
    "span_missing",
    "unsupported_claim_not_detected",
    "false_abstention",
    "answer_mismatch",
    "citation_miss",
    "route_unavailable",
)
```

- [ ] **Step 3: Run diagnostics tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_metrics.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  -q
```

Expected: QASPER and ALCE are not penalized for missing page labels; FinanceBench can still report page/locator errors when page evidence exists.

### Task 5: Make Citation Metrics Match Citation Target

**Files:**

- Modify: `benchmark/citation_metrics.py`
- Modify: `benchmark/scoring.py`
- Modify: `benchmark/reports.py`
- Modify: `benchmark/tests/test_scoring.py`
- Modify: `benchmark/tests/test_reports_diagnostics.py`

- [ ] **Step 1: Add source/page/span citation tests**

```python
def test_source_level_citation_does_not_require_page_exact_match():
    prediction = {
        "predicted_sources": ["paper-1"],
        "gold_evidence": [{"document_id": "paper-1", "span": "The answer span."}],
        "retrieved_hits": [{"source_id": "paper-1", "text": "The answer span."}],
        "evidence_bundle": {"items": []},
    }

    assert citation_recall_score(
        prediction["predicted_sources"],
        prediction["gold_evidence"],
        retrieved_hits=prediction["retrieved_hits"],
        evidence_bundle=prediction["evidence_bundle"],
    ) == 1.0


def test_page_level_citation_requires_page_when_gold_has_page_locator():
    prediction = {
        "predicted_sources": ["report#page:9"],
        "gold_evidence": [{"document_id": "report", "page": 5}],
        "retrieved_hits": [{"source_id": "report", "page_label": "9"}],
        "evidence_bundle": {"items": []},
    }

    assert citation_recall_score(
        prediction["predicted_sources"],
        prediction["gold_evidence"],
        retrieved_hits=prediction["retrieved_hits"],
        evidence_bundle=prediction["evidence_bundle"],
    ) == 0.0
```

- [ ] **Step 2: Report submetrics instead of one ambiguous number**

Ensure `route_metrics.csv` and `report.md` include:

```text
citation_recall_source
citation_recall_page
citation_recall_span
citation_precision_source
citation_precision_page
citation_precision_span
```

- [ ] **Step 3: Run citation/scoring tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_reports_diagnostics.py \
  -q
```

Expected: ALCE/QASPER source-level citation can pass without page exactness; FinanceBench page exactness remains visible as a page-level submetric.

### Task 6: Verify Final Answers, Not Thought Traces

**Files:**

- Modify: `libs/ktem/ktem/docqa/evidence_text.py`
- Modify: `libs/ktem/ktem/docqa/verification.py`
- Modify: `libs/ktem/ktem/docqa/domain_verifiers.py`
- Modify: `benchmark/scoring.py`
- Modify: `benchmark/verification_metrics.py`
- Modify: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`
- Modify: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Add final-answer extraction tests**

```python
def test_extract_final_answer_removes_think_blocks_and_keeps_numeric_result():
    answer = """<think>
    I will compute an intermediate ratio incorrectly.
    </think>

    Final answer: The quick ratio is 1.42."""

    assert extract_final_answer_text(answer) == "The quick ratio is 1.42."
```

- [ ] **Step 2: Add verifier/scorer regression coverage**

```python
def test_scorer_uses_final_answer_not_reasoning_trace():
    metrics = score_prediction(
        {
            "predicted_answer": "<think>wrong: 9</think>\nFinal answer: 42",
            "gold_answers": ["42"],
            "predicted_pages": [],
            "gold_pages": [],
            "predicted_sources": [],
            "gold_sources": [],
            "gold_evidence": [],
        }
    )

    assert metrics["em"] == 1.0
```

- [ ] **Step 3: Keep domain verifier opt-in explicit**

Domain verifiers should be selected only from request/manifest config:

```python
def verifier_for_domain(domain: str | None) -> Callable[[VerificationInput], VerificationResult]:
    if str(domain or "").strip().lower() == "finance":
        return verify_finance_answer
    return verify_generic_answer
```

- [ ] **Step 4: Run verifier and scoring tests**

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  benchmark/tests/test_scoring.py \
  -q
```

Expected: hidden thought traces do not affect verifier/scorer metrics, and finance verifier behavior remains opt-in.

### Task 7: Keep Controller Policy Generic

**Files:**

- Modify: `libs/ktem/ktem/docqa/controller.py`
- Modify: `libs/ktem/ktem/docqa/retrieval_adequacy.py`
- Modify: `libs/ktem/ktem/docqa/hybrid_fusion.py`
- Modify: `libs/ktem/ktem/reasoning/mara_controller.py`
- Modify: `benchmark/manifest_templates.py`
- Modify: `benchmark/tests/test_manifest_templates.py`
- Modify: `libs/ktem/ktem_tests/test_docqa_controller.py`
- Modify: `libs/ktem/ktem_tests/test_docqa_controller_route_switch.py`
- Modify: `libs/ktem/ktem_tests/test_docqa_hybrid_fusion.py`

- [ ] **Step 1: Add controller allowlist contract**

```python
def test_controller_default_benchmark_allowlist_is_domain_neutral():
    assert CONTROLLER_ALLOWED_ROUTES == (
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    )
```

- [ ] **Step 2: Add retrieval adequacy domain tests**

```python
def test_retrieval_adequacy_is_empty_without_finance_domain():
    issue = retrieval_adequacy_issue(
        "What is the quick ratio?",
        {"evidence": [{"text": "current assets"}]},
        domain=None,
    )

    assert issue == ""


def test_retrieval_adequacy_can_apply_finance_domain_when_requested():
    issue = retrieval_adequacy_issue(
        "What is the quick ratio?",
        {"evidence": [{"text": "current assets"}]},
        domain="finance",
    )

    assert "financial statement" in issue
```

- [ ] **Step 3: Add hybrid fusion domain tests**

```python
def test_hybrid_fusion_does_not_apply_finance_boost_without_domain():
    fused, trace = fuse_hybrid_evidence(
        "quick ratio current assets",
        [{"evidence_id": "a", "text": "current assets", "modality": "text"}],
        domain=None,
    )

    components = fused[0]["metadata"]["hybrid_fusion_components"]
    assert components["finance_statement_match"] == 0.0
```

- [ ] **Step 4: Run controller tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_manifest_templates.py \
  libs/ktem/ktem_tests/test_docqa_controller.py \
  libs/ktem/ktem_tests/test_docqa_controller_route_switch.py \
  libs/ktem/ktem_tests/test_docqa_hybrid_fusion.py \
  -q
```

Expected: controller route policy is the same across FinanceBench, QASPER, RAGTruth, and ALCE unless manifest capabilities make a route unavailable.

### Task 8: Build Cross-Dataset Contract Fixtures

**Files:**

- Create: `benchmark/tests/test_cross_dataset_contracts.py`
- Modify: `benchmark/tests/test_runner_sampling_summary.py`
- Modify: `benchmark/tests/test_research_evaluators.py`

- [ ] **Step 1: Add one synthetic case per dataset shape**

Use records with the smallest useful evidence shape:

```python
CROSS_DATASET_CASES = {
    "financebench": {
        "gold_evidence": [{"document_id": "report", "page": 5, "span": "Revenue was 10."}],
        "capabilities": {"page_evidence": True, "span_evidence": True},
    },
    "qasper": {
        "gold_evidence": [{"document_id": "paper", "span": "The model uses retrieval."}],
        "capabilities": {"source_level_citations": True, "span_evidence": True},
    },
    "ragtruth": {
        "gold_evidence": [{"document_id": "doc", "span": "The claim is unsupported.", "support_label": "unsupported"}],
        "capabilities": {"hallucination_labels": True, "supports_abstention": True},
    },
    "alce": {
        "gold_evidence": [{"document_id": "source-1", "span": "The attributed answer span."}],
        "capabilities": {"citation_quality": True, "source_level_citations": True},
    },
}
```

- [ ] **Step 2: Assert every case can produce diagnostics**

```python
@pytest.mark.parametrize("dataset_family,case", CROSS_DATASET_CASES.items())
def test_cross_dataset_case_gets_failure_class(dataset_family, case):
    prediction = prediction_from_case(dataset_family, case)

    normalize_prediction_diagnostics(prediction)

    assert prediction["diagnostics"]["failure_class"] in FAILURE_CLASSES
```

- [ ] **Step 3: Run the contract fixtures**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_cross_dataset_contracts.py \
  benchmark/tests/test_runner_sampling_summary.py \
  benchmark/tests/test_research_evaluators.py \
  -q
```

Expected: one generic prediction contract covers all four dataset shapes.

### Task 9: Run Focused Validation Gates

**Files:**

- No code changes unless a gate exposes a regression.

- [ ] **Step 1: Run the focused Python gate**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_index_metadata.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  libs/ktem/ktem_tests/test_docqa_controller.py \
  libs/ktem/ktem_tests/test_docqa_controller_route_switch.py \
  libs/ktem/ktem_tests/test_docqa_hybrid_fusion.py \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  -q
```

Expected: PASS. Do not use repo-root `pytest -q` as readiness signal.

- [ ] **Step 2: Run hygiene on changed Python files**

```bash
uv run --python 3.10 python scripts/check_codebase_hygiene.py \
  benchmark/dataset_profiles.py \
  benchmark/evidence_adapters.py \
  benchmark/docqa_evidence_projection.py \
  benchmark/docqa_runtime_sources.py \
  benchmark/index_metadata.py \
  benchmark/page_alignment.py \
  benchmark/citation_metrics.py \
  benchmark/scoring.py \
  benchmark/diagnostics.py \
  benchmark/reports.py \
  benchmark/runner.py \
  libs/ktem/ktem/docqa/evidence_text.py \
  libs/ktem/ktem/docqa/verification.py \
  libs/ktem/ktem/docqa/domain_verifiers.py \
  libs/ktem/ktem/docqa/retrieval_adequacy.py \
  libs/ktem/ktem/docqa/hybrid_fusion.py \
  libs/ktem/ktem/docqa/controller.py \
  libs/ktem/ktem/reasoning/mara_controller.py \
  libs/ktem/ktem/reasoning/mara_route_retrieval.py
```

Expected: no ratchet violations. Do not update `scripts/codebase_hygiene_baseline.json`.

- [ ] **Step 3: Run pre-commit on changed files**

```bash
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

Expected: PASS.

### Task 10: Run Small Cross-Dataset Benchmark Gate

**Files:**

- Slurm scripts only under `~/scratch/outputs/MARA/slurm/scripts/`
- Reports only under `~/scratch/outputs/MARA/reports/`
- Artifacts only under `~/scratch/outputs/MARA/artifacts/`

- [ ] **Step 1: Submit one 10-sample chain**

Use current manifests for all four datasets with the same code revision and route template family. Prefer the strongest idle GPU, but keep outputs under scratch:

```bash
sbatch ~/scratch/outputs/MARA/slurm/scripts/<cross_dataset_10sample_script>.sh
```

Expected: jobs start from `~/scratch/projects/MARA`; no outputs are written under `~/data` or the repo.

- [ ] **Step 2: Validate artifacts**

Run an artifact validator that checks:

```python
assert all_prediction_rows_have("diagnostics.failure_class")
assert no_visible_field_contains("<think>")
assert no_prediction_contains("data:image")
assert no_prediction_contains("base64")
assert controller_routes_are_within_manifest_allowlist()
assert no_finance_adequacy_reason_without_verification_domain_finance()
```

- [ ] **Step 3: Write a cross-dataset gate report**

Create `~/scratch/outputs/MARA/reports/cross_dataset_generalization_10sample_<timestamp>.md` with:

```markdown
# Cross-Dataset Generalization 10-Sample Gate

## Dataset Metrics

## Retrieval Failure Classes

## Evidence/Citation Shape Checks

## Verifier Thought-Leak Checks

## Controller Route Checks

## Finance-Specific Boundary Checks

## Decision
```

Expected decision: proceed only if the gate shows no Finance-specific generic leakage and no payload/thought leakage.

### Task 11: Scale Only After The 10-Sample Gate Is Clean

**Files:**

- Slurm scripts only under `~/scratch/outputs/MARA/slurm/scripts/`
- Reports only under `~/scratch/outputs/MARA/reports/`

- [ ] **Step 1: Run 50-sample current chain**

Use the same validation criteria as Task 10, but increase sample size to 50.

- [ ] **Step 2: Compare against the previous Finance-leaning run**

Report these deltas by dataset and route:

```text
avg_f1
citation_recall_source
citation_recall_page
citation_recall_span
not_enough_evidence_rate
false_abstention_rate
no_retrieved_hits_rate
source_miss_rate
wrong_locator_rate
controller_route_violation_count
finance_leak_count
think_leak_count
image_payload_leak_count
```

- [ ] **Step 3: Decide next optimization target**

Only optimize a subsystem if the failure pattern appears in at least two dataset families, or if it is isolated behind a dataset adapter/domain-opt-in boundary.

## Final Verification Checklist

Before claiming the implementation is ready:

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
uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-files>
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

If MARA or `MARA-cli` command behavior changes, also run the relevant contract tests in `libs/slide_cli`.

## Self-Review

- Spec coverage: the plan covers retrieval, evidence, citation, verifier, and controller across FinanceBench, QASPER, RAGTruth, and ALCE.
- Boundary coverage: generic code is protected by explicit tests against FinanceBench leakage.
- Storage coverage: preflight and output locations are specified before tests and Slurm.
- Public surface coverage: benchmark JSON/report surfaces are identified; MARA CLI, Gradio, DB, and session shapes are marked unaffected unless later changes expand scope.
- Large-code policy: expected fixtures and metric matrices are legitimate large code if kept readable and isolated in tests or data definitions.
