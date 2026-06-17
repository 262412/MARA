# Generic Cross-Dataset Benchmark Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate and improve MARA retrieval, evidence, citation, verifier, and controller behavior across FinanceBench, QASPER, RAGTruth, ALCE, and future multimodal datasets without encoding FinanceBench-specific behavior in generic runtime paths.

**Architecture:** Represent dataset differences as capability profiles and normalized evidence records. Dataset-specific code is allowed only at import/normalization and fixture boundaries; runtime retrieval, evidence projection, scoring, verifier cleanup, and controller routing must branch on data shape and capability flags.

**Tech Stack:** Python 3.10, existing `benchmark` package, MARA DocQA runtime under `libs/ktem`, JSON v2 manifests, pytest, `scripts/check_codebase_hygiene.py`, pre-commit, Slurm artifacts under `~/scratch/outputs/MARA`.

---

## Operating Rules

Do not optimize for FinanceBench alone.

Allowed dataset-specific code:

- `benchmark/financebench_*` importers, page-normalization helpers, fixtures, and tests.
- QASPER/RAGTruth/ALCE importers or fixtures when needed.
- Report labels and manifest dataset identifiers.

Forbidden dataset-specific code:

- `if dataset_name == "financebench"` in generic retrieval, evidence projection, scoring, verifier, controller, or route-selection logic.
- Generic modules importing `benchmark.financebench_*`.
- Verifier or scorer rules that only work because FinanceBench answers are numeric or page-labeled.
- Route templates that hide failures by silently swapping a required baseline route for a better route.

Current drift reset rule:

- Before implementing new fixes, audit the current dirty worktree for Finance-tuned behavior.
- Keep a change only if it improves a data-shape capability that at least two dataset families can use, or if it is isolated to a dataset adapter/test fixture.
- Move Finance-only behavior to `benchmark/financebench_*` or an explicitly opt-in domain verifier.
- Do not optimize aggregate score if the change weakens QASPER, RAGTruth, ALCE, or future source-level/multimodal evidence behavior.

The implementation must preserve:

- `MARA` and `MARA-cli` public command surface.
- Existing DocQA runtime request/session shapes unless a task explicitly introduces a tested compatibility field.
- Manifest JSON backward compatibility where existing fields are already public artifacts.
- Output location discipline: datasets and artifacts stay outside the repository.

## Public Surface

Affected surfaces:

- Benchmark manifest JSON profile/capability metadata.
- Route templates and allowed route sets.
- Prediction JSONL keys for evidence, citations, diagnostics, verifier, and controller metadata.
- `summary.json`, route metrics, and Markdown report diagnostic fields.
- DocQA benchmark runtime evidence projection and verifier input cleanup.

Unaffected surfaces:

- Public `MARA` / `MARA-cli` command names and top-level option names.
- Gradio event order.
- App DB schema.
- Persisted interactive session shape.

## Preflight Gate

Run before any `uv`, test, indexing, model call, dataset sync, or Slurm job:

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

- Repository resolves to `/mnt/scratch/users/tbczhang/projects/MARA`.
- `.venv` resolves to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Caches and runtime data point to fastscratch, except `PRE_COMMIT_HOME` under scratch.
- fastscratch, scratch, and data quotas are below soft limits.
- The repository root has no `data`, `datasets`, or `outputs` directory.

## Failure Taxonomy

Use one shared taxonomy across FinanceBench, QASPER, RAGTruth, ALCE, and multimodal datasets:

| Failure                     | Meaning                                                            | Fix direction                                                                      |
| --------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `execution_error`           | Runtime failed before a valid prediction                           | Fix config, backend, request shape, or context budget                              |
| `no_retrieved_hits`         | Retriever returned no usable evidence                              | Fix query construction, selected-file scope, index metadata, or retriever fallback |
| `wrong_source`              | Evidence exists but source/document identity is wrong              | Fix source ID normalization and manifest-document mapping                          |
| `missing_locator_metadata`  | Evidence lacks page/span/source locator fields required by profile | Fix parser/index metadata projection                                               |
| `wrong_locator`             | Source is right but page/section/locator is wrong                  | Fix locator alignment, reranking, or chunk metadata                                |
| `gold_span_missing`         | Source/locator may be right but support text is absent             | Fix chunking, retrieval depth, text extraction, or span normalization              |
| `citation_miss`             | Evidence supports answer but emitted citation does not match       | Fix citation normalization and source-level/page-level citation matching           |
| `verifier_over_abstention`  | Supported final answer is rejected                                 | Fix final-answer extraction or generic support matching                            |
| `verifier_under_abstention` | Unsupported final answer passes                                    | Fix claim extraction and contradiction/unsupported detection                       |
| `controller_route_mismatch` | Controller chooses route outside profile capability                | Fix route gating, capability metadata, or route decision prompt                    |

## File Responsibility Map

- `benchmark/dataset_profiles.py`: data-shape profiles and allowed route capabilities.
- `benchmark/evidence_adapters.py`: normalized gold evidence records from source/page/span/citation/hallucination inputs.
- `benchmark/page_alignment.py`: generic page/locator alignment helpers.
- `benchmark/citation_metrics.py`: citation matching by source, page, locator, and source-level references.
- `benchmark/diagnostics.py`: shared failure taxonomy assignment.
- `benchmark/scoring.py`: metric assembly over cleaned final answers and normalized evidence.
- `benchmark/summary.py`: aggregate metrics by dataset, route, capability, and failure class.
- `benchmark/reports.py`: human-readable route/failure reports.
- `benchmark/manifest.py`: manifest loading with profile metadata.
- `benchmark/manifest_templates.py`: route template composition from capability profiles.
- `benchmark/docqa_evidence_projection.py`: runtime evidence bundle projection to benchmark evidence records.
- `benchmark/docqa_runtime_sources.py`: benchmark-only runtime source extraction and artifact capture.
- `benchmark/engines.py`: engine request/response boundary and route metadata propagation.
- `libs/ktem/ktem/docqa/evidence_text.py`: answer/thinking cleanup and evidence text normalization.
- `libs/ktem/ktem/docqa/verification.py`: generic verifier over final answer and normalized evidence.
- `libs/ktem/ktem/docqa/domain_verifiers.py`: explicit opt-in domain verifier registry, never default Finance logic.
- `libs/ktem/ktem/reasoning/mara_route_retrieval.py`: route capability gating and modality-safe evidence handoff.
- `libs/ktem/ktem/reasoning/mara_controller.py`: controller allowed-route policy and route-switch trace.

---

### Task 0: Audit And Stop Finance-Tuned Drift

**Files:**

- Review only: `benchmark/*.py`
- Review only: `libs/ktem/ktem/docqa/*.py`
- Review only: `libs/ktem/ktem/reasoning/*.py`
- Create or update: `benchmark/tests/test_no_finance_specialization_boundaries.py`

- [x] **Step 1: Snapshot the current changed files**

```bash
git status --short
```

Expected: collect the existing modified and untracked files before editing. Do not revert user changes.

- [x] **Step 2: Classify each existing benchmark/runtime change**

Create a local checklist in the implementation notes with exactly one category per change:

```text
generic-capability: improves source/page/span/multimodal/layout evidence for multiple dataset families
dataset-adapter: belongs in FinanceBench/QASPER/RAGTruth/ALCE-specific import or fixture code
domain-opt-in: belongs behind an explicit manifest/profile verifier flag
reject-or-isolate: makes generic runtime narrower or score-tuned for one dataset
```

Expected: no generic runtime change proceeds without one of the first three categories.

- [x] **Step 3: Add the specialization boundary test before further fixes**

Use the AST test in Task 1 before editing generic retrieval, evidence, verifier, scoring, or controller modules.

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected: current failures identify Finance-specific leakage. A passing result becomes the guard for later tasks.

- [x] **Step 4: Move or isolate Finance-only behavior**

For each `dataset-adapter` or `domain-opt-in` item:

```text
FinanceBench page-label repair -> benchmark/financebench_pages.py or benchmark/financebench_evidence.py
Finance numeric tolerance -> libs/ktem/ktem/docqa/domain_verifiers.py behind profile flag
Finance-specific report labels -> report rendering only, never scoring logic
```

Expected: generic modules consume normalized evidence/profile fields and do not depend on FinanceBench names.

- [x] **Step 5: Re-run cross-dataset focused tests before any score work**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_scoring.py \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  -q
```

Expected: boundary, evidence shape, locator, scoring, and verifier behavior pass before benchmark score tuning resumes.

### Task 1: Lock Finance-Specific Boundary

**Files:**

- Create or update: `benchmark/tests/test_no_finance_specialization_boundaries.py`

- [x] **Step 1: Write the boundary test**

Use AST import checks so generic modules cannot import FinanceBench adapters:

```python
from __future__ import annotations

import ast
from pathlib import Path


GENERIC_MODULES = (
    "benchmark/citation_metrics.py",
    "benchmark/diagnostics.py",
    "benchmark/docqa_evidence_projection.py",
    "benchmark/docqa_runtime_sources.py",
    "benchmark/engines.py",
    "benchmark/manifest.py",
    "benchmark/manifest_templates.py",
    "benchmark/metrics.py",
    "benchmark/page_alignment.py",
    "benchmark/reports.py",
    "benchmark/scoring.py",
    "benchmark/summary.py",
    "libs/ktem/ktem/docqa/evidence_text.py",
    "libs/ktem/ktem/docqa/verification.py",
    "libs/ktem/ktem/reasoning/mara_controller.py",
    "libs/ktem/ktem/reasoning/mara_route_retrieval.py",
)


def test_generic_modules_do_not_import_financebench_adapters():
    repo = Path(__file__).resolve().parents[2]
    offenders = []

    for relative_path in GENERIC_MODULES:
        path = repo / relative_path
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _imports_finance_module(tree):
            offenders.append(relative_path)

    assert offenders == []


def _imports_finance_module(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_is_finance_module(alias.name) for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if _is_finance_module(node.module or ""):
                return True
    return False


def _is_finance_module(module: str) -> bool:
    return any(part.startswith("finance") for part in module.split("."))
```

- [x] **Step 2: Run the boundary test**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected: fails only if generic modules import FinanceBench-specific code.

- [x] **Step 3: Move any offending imports**

Keep FinanceBench-specific parsing in:

```text
benchmark/financebench_evidence.py
benchmark/financebench_pages.py
benchmark/tests/test_financebench_*.py
```

Generic modules must consume normalized records, not FinanceBench helpers.

- [x] **Step 4: Re-run**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_no_finance_specialization_boundaries.py -q
```

Expected: pass.

### Task 2: Define Capability Profiles

**Files:**

- Modify: `benchmark/dataset_profiles.py`
- Modify: `benchmark/manifest.py`
- Test: `benchmark/tests/test_dataset_profiles.py`

- [x] **Step 1: Add profile contract tests**

```python
def test_profiles_are_data_shape_capabilities():
    finance = profile_for_dataset("financebench")
    qasper = profile_for_dataset("qasper")
    ragtruth = profile_for_dataset("ragtruth")
    alce = profile_for_dataset("alce")

    assert finance.capabilities.page_locator is True
    assert finance.capabilities.source_level_citation is False

    assert qasper.capabilities.span_evidence is True
    assert qasper.capabilities.page_locator is False

    assert ragtruth.capabilities.source_level_citation is True
    assert ragtruth.capabilities.verification_labels is True

    assert alce.capabilities.source_level_citation is True
    assert alce.capabilities.attributable_generation is True


def test_allowed_routes_come_from_capabilities():
    profile = profile_for_dataset("financebench")

    assert profile.allowed_routes == (
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    )
```

- [x] **Step 2: Implement profile dataclasses**

Add explicit, generic fields:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetCapabilities:
    page_locator: bool = False
    span_evidence: bool = False
    source_level_citation: bool = False
    verification_labels: bool = False
    attributable_generation: bool = False
    multimodal_pages: bool = False
    layout_elements: bool = False


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    family: str
    capabilities: DatasetCapabilities
    allowed_routes: tuple[str, ...]
```

The implementation may map known dataset names to profiles, but downstream code must only inspect `capabilities` and `allowed_routes`.

- [x] **Step 3: Attach profile metadata at manifest load**

In `benchmark/manifest.py`, keep raw manifest fields unchanged and attach:

```python
profile = profile_for_dataset(manifest.dataset_name)
manifest.metadata["dataset_profile"] = profile.name
manifest.metadata["capabilities"] = profile.capabilities.__dict__
manifest.metadata["allowed_routes"] = list(profile.allowed_routes)
```

- [x] **Step 4: Run tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_dataset_profiles.py -q
```

Expected: profile contract passes for FinanceBench, QASPER, RAGTruth, and ALCE.

### Task 3: Normalize Gold Evidence Across Data Shapes

**Files:**

- Modify: `benchmark/evidence_adapters.py`
- Modify: `benchmark/scoring.py`
- Test: `benchmark/tests/test_evidence_adapters.py`

- [ ] **Step 1: Add evidence adapter tests**

```python
def test_normalizes_page_span_evidence():
    raw = {"document_id": "amd-2021", "page": 58, "span": "cash flow"}

    record = normalize_gold_evidence(raw)

    assert record.source_id == "amd-2021"
    assert record.page_label == "58"
    assert record.text_span == "cash flow"
    assert record.citation == "amd-2021#page=58"


def test_normalizes_source_level_evidence():
    raw = {"document_id": "14864", "span": "Yelp", "citation": "14864#source"}

    record = normalize_gold_evidence(raw)

    assert record.source_id == "14864"
    assert record.page_label is None
    assert record.text_span == "Yelp"
    assert record.citation == "14864#source"
    assert record.locator_kind == "source"
```

- [ ] **Step 2: Implement a normalized evidence dataclass**

```python
@dataclass(frozen=True)
class EvidenceRecord:
    source_id: str
    citation: str | None = None
    text_span: str | None = None
    page_label: str | None = None
    parser_page_index: int | None = None
    locator_kind: str = "source"
```

- [ ] **Step 3: Route all scoring through normalized evidence**

In `benchmark/scoring.py`, convert gold evidence once near input parsing:

```python
gold_records = [normalize_gold_evidence(item) for item in prediction.gold_evidence]
```

Do not branch on dataset names. Branch on fields such as `page_label`, `text_span`, and `locator_kind`.

- [ ] **Step 4: Run adapter/scoring tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_evidence_adapters.py benchmark/tests/test_scoring.py -q
```

Expected: FinanceBench page evidence and RAGTruth/ALCE source-level evidence score through the same record type.

### Task 4: Make Locator Alignment Generic

**Files:**

- Modify: `benchmark/page_alignment.py`
- Modify: `benchmark/docqa_evidence_projection.py`
- Test: `benchmark/tests/test_page_alignment.py`

- [ ] **Step 1: Add locator alignment tests**

```python
def test_aligns_gold_page_label_to_parser_page_index():
    metadata = {"page_label": "58", "page": 57}

    aligned = align_locator(gold_page="58", retrieved_metadata=metadata)

    assert aligned.page_exact is True
    assert aligned.parser_page_index == 57


def test_source_level_locator_does_not_require_page():
    metadata = {"source_id": "14864"}

    aligned = align_locator(gold_page=None, retrieved_metadata=metadata)

    assert aligned.locator_applicable is False
    assert aligned.page_exact is None
```

- [ ] **Step 2: Implement `LocatorAlignment`**

```python
@dataclass(frozen=True)
class LocatorAlignment:
    locator_applicable: bool
    page_exact: bool | None
    parser_page_index: int | None
```

- [ ] **Step 3: Project page labels without assuming FinanceBench**

Use metadata fields in priority order:

```python
PAGE_LABEL_KEYS = ("page_label", "page_number_label", "source_page_label")
PAGE_INDEX_KEYS = ("parser_page_index", "page", "page_index")
```

If no page label exists and the profile does not require page evidence, classify the locator as not applicable, not wrong.

- [ ] **Step 4: Run locator tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_page_alignment.py benchmark/tests/test_docqa_runtime_engine_sources.py -q
```

Expected: page-based and source-level datasets receive distinct locator diagnostics.

### Task 5: Fix Retrieval Evidence Projection Without Modality Leakage

**Files:**

- Modify: `benchmark/docqa_evidence_projection.py`
- Modify: `benchmark/docqa_runtime_sources.py`
- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Test: `benchmark/tests/test_docqa_runtime_engine_sources.py`

- [ ] **Step 1: Add tests for text-safe evidence projection**

```python
def test_text_route_does_not_send_image_payload_to_llm():
    evidence = project_runtime_evidence(
        route="doc_text",
        raw_items=[{"text": "Revenue increased", "image": "base64-image"}],
    )

    assert evidence[0].text == "Revenue increased"
    assert "image" not in evidence[0].llm_payload


def test_source_level_short_document_can_be_represented_as_text_evidence():
    evidence = project_selected_source_evidence(
        source_id="14864",
        text="Yelp",
        route="doc_text",
    )

    assert evidence[0].source_id == "14864"
    assert evidence[0].text == "Yelp"
    assert evidence[0].citation == "14864#source"
```

- [ ] **Step 2: Implement modality-safe projection**

For LLM text context, pass only text fields:

```python
llm_payload = {"text": item.text, "source_id": item.source_id}
```

Keep image/page payloads only in separate visual route metadata for VLM-capable routes.

- [ ] **Step 3: Add generic selected-source fallback**

If all of these are true:

- route requires textual evidence,
- selected file scope contains exactly one source,
- retriever returns no usable chunks,
- selected source text is non-empty and below the configured short-source threshold,

then emit a source-level evidence record. This is generic source-level behavior for short documents, not a RAGTruth special case.

- [ ] **Step 4: Run projection tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_docqa_runtime_engine_sources.py -q
```

Expected: no image payload in text LLM path; short source-level text can be represented as evidence.

### Task 6: Clean Final Answers Before Verification And Scoring

**Files:**

- Modify: `libs/ktem/ktem/docqa/evidence_text.py`
- Modify: `libs/ktem/ktem/docqa/verification.py`
- Modify: `benchmark/scoring.py`
- Test: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`
- Test: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Add cleanup regressions**

```python
def test_removes_think_block_before_verification():
    answer = "<think>compute silently</think>\nFinal answer: Revenue was $10 million."

    assert extract_final_answer_text(answer) == "Revenue was $10 million."


def test_scoring_uses_final_answer_not_reasoning_trace():
    score = score_answer(
        prediction="<think>wrong intermediate value</think>\nFinal answer: 42.0%",
        references=["42%"],
    )

    assert score.f1 > 0.5
```

- [ ] **Step 2: Implement one cleanup function**

```python
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def extract_final_answer_text(text: str) -> str:
    cleaned = THINK_BLOCK_RE.sub("", text or "").strip()
    marker = "Final answer:"
    if marker.lower() in cleaned.lower():
        return cleaned.split(marker, 1)[-1].strip()
    return cleaned
```

If case-insensitive splitting is needed, implement it once in this helper and cover it in tests.

- [ ] **Step 3: Route verifier and scorer through the helper**

Use the same cleaned answer for:

- verifier claim extraction,
- unsupported/contradiction checks,
- answer F1/EM scoring,
- report answer preview.

- [ ] **Step 4: Run cleanup tests**

```bash
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_docqa_verification_regressions.py benchmark/tests/test_scoring.py -q
```

Expected: no `<think>` content reaches verifier/scorer metrics.

### Task 7: Make Verifier Generic And Domain Verifiers Opt-In

**Files:**

- Modify: `libs/ktem/ktem/docqa/verification.py`
- Modify: `libs/ktem/ktem/docqa/domain_verifiers.py`
- Modify: `benchmark/verification_metrics.py`
- Test: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`

- [ ] **Step 1: Add opt-in domain verifier tests**

```python
def test_default_verifier_does_not_use_finance_numeric_rules():
    decision = verify_answer(
        answer="The source is Yelp.",
        evidence_texts=["Yelp"],
        profile=None,
    )

    assert decision.is_supported is True


def test_domain_verifier_requires_explicit_profile_flag():
    registry = DomainVerifierRegistry()

    assert registry.select(profile_flags={}) is registry.generic
    assert registry.select(profile_flags={"domain_verifier": "finance"}) is registry.finance
```

- [ ] **Step 2: Keep generic verifier as default**

Generic verifier criteria:

- compare cleaned final answer claims with retrieved evidence text,
- allow source-level support when the evidence text is the source itself,
- classify unsupported only when evidence contradicts or lacks the final claim.

- [ ] **Step 3: Register domain verifiers explicitly**

`domain_verifiers.py` may contain a Finance verifier, but it must only be selected when a manifest/route explicitly requests it.

- [ ] **Step 4: Run verifier tests**

```bash
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_docqa_verification_regressions.py -q
```

Expected: RAGTruth/ALCE source-level evidence is not rejected by Finance numeric heuristics.

### Task 8: Enforce Controller Route Capabilities

**Files:**

- Modify: `benchmark/manifest_templates.py`
- Modify: `benchmark/controller_fields.py`
- Modify: `libs/ktem/ktem/reasoning/mara_controller.py`
- Test: `benchmark/tests/test_manifest_templates.py`
- Test: `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`

- [ ] **Step 1: Add allowed-route tests**

```python
def test_text_financial_profile_allows_generic_routes():
    routes = allowed_routes_for_profile(profile_for_dataset("financebench"))

    assert routes == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]


def test_controller_cannot_select_route_outside_profile():
    decision = select_controller_route(
        question="What is shown in the chart?",
        allowed_routes=["doc_text", "hybrid"],
    )

    assert decision.route in {"doc_text", "hybrid"}
```

- [ ] **Step 2: Configure route templates from profiles**

For `controller_auto`, pass:

```python
allowed_routes = profile.allowed_routes
```

The FinanceBench-compatible set is the generic text-document set:

```python
("doc_text", "hybrid", "doc_page_image", "doc_element", "graph_global")
```

Do not hard-code this set only for FinanceBench. Use it for any profile whose capabilities include text documents with optional page/layout/graph support.

- [ ] **Step 3: Record route decisions**

Controller predictions must include:

```json
{
  "allowed_routes": ["doc_text", "hybrid"],
  "selected_route": "hybrid",
  "route_switches": ["doc_text", "hybrid"],
  "route_policy_reason": "retrieval evidence missing"
}
```

- [ ] **Step 4: Run controller tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_manifest_templates.py libs/ktem/ktem_tests/test_mara_controller_route_extensions.py -q
```

Expected: controller respects capability-derived route gates and exposes traceable route decisions.

### Task 9: Improve Citation Metrics By Locator Kind

**Files:**

- Modify: `benchmark/citation_metrics.py`
- Modify: `benchmark/metrics.py`
- Modify: `benchmark/scoring.py`
- Test: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Add citation matching tests**

```python
def test_page_level_citation_match_requires_source_and_page():
    gold = EvidenceRecord(source_id="amd", citation="amd#page=58", page_label="58")
    pred = EvidenceRecord(source_id="amd", citation="amd#page=58", page_label="58")

    assert citation_match(gold, pred).exact is True


def test_source_level_citation_match_does_not_require_page():
    gold = EvidenceRecord(source_id="14864", citation="14864#source")
    pred = EvidenceRecord(source_id="14864", citation="14864#source")

    assert citation_match(gold, pred).exact is True
```

- [ ] **Step 2: Implement locator-kind-aware matching**

Rules:

- page-level evidence requires normalized source ID plus aligned page label,
- source-level evidence requires normalized source ID,
- span-level evidence prefers source ID plus normalized span overlap,
- multimodal/page-image evidence requires page/source ID and modality tag.

- [ ] **Step 3: Report citation submetrics**

Add route metrics:

```text
citation_recall_source
citation_recall_page
citation_recall_span
citation_precision_source
citation_precision_page
citation_precision_span
```

- [ ] **Step 4: Run scoring tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_scoring.py -q
```

Expected: FinanceBench page citations and ALCE/RAGTruth source citations are both evaluated correctly without dataset-name checks.

### Task 10: Add Cross-Dataset Diagnostics Reports

**Files:**

- Modify: `benchmark/diagnostics.py`
- Modify: `benchmark/summary.py`
- Modify: `benchmark/reports.py`
- Test: `benchmark/tests/test_runner_diagnostics.py`
- Test: `benchmark/tests/test_reports_diagnostics.py`

- [ ] **Step 1: Add report tests**

```python
def test_summary_groups_failures_by_capability_and_route():
    summary = summarize_diagnostics(
        [
            {"dataset": "financebench", "route": "text_rag", "failure": "wrong_locator"},
            {"dataset": "ragtruth", "route": "text_rag", "failure": "no_retrieved_hits"},
        ]
    )

    assert summary["failure_counts"]["wrong_locator"] == 1
    assert summary["failure_counts"]["no_retrieved_hits"] == 1
```

- [ ] **Step 2: Emit route-level diagnostic tables**

Reports must include:

- dataset x route x failure class counts,
- route switch rate,
- verifier over-abstention and under-abstention,
- citation miss by locator kind,
- retrieval hit count and source-hit/page-hit/span-hit.

- [ ] **Step 3: Keep score tables separate from diagnostic tables**

Do not hide low score behind aggregated pass/fail. The report should show whether a low score came from retrieval, citation formatting, verifier abstention, or controller route choice.

- [ ] **Step 4: Run diagnostics tests**

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_runner_diagnostics.py benchmark/tests/test_reports_diagnostics.py -q
```

Expected: summary/report artifacts explain failures by generic class across all four datasets.

### Task 11: Run 1-Sample Readiness Matrix

**Files:**

- No code files should change in this task.
- Outputs must go under `~/scratch/outputs/MARA`.

- [ ] **Step 1: Run FinanceBench readiness**

```bash
uv run --python 3.10 python -m benchmark run \
  --manifest benchmark/manifests/financebench-main.json \
  --route-template benchmark/manifests/templates/mara_text_only.json \
  --limit 1 \
  --output-dir ~/scratch/outputs/MARA/artifacts/plan5-financebench-1sample-generic
```

Expected:

- no execution error,
- no `<think>` in verifier/scorer input,
- no image payload in text LLM context,
- diagnostics classify any score loss.

- [ ] **Step 2: Run QASPER readiness**

Use the QASPER manifest generated under `~/scratch/outputs/MARA/manifests/plan5/qasper`.

Expected:

- retrieved evidence has source identity,
- span evidence is scored without requiring pages,
- controller route is inside allowed routes.

- [ ] **Step 3: Run RAGTruth readiness**

Use the RAGTruth manifest generated under `~/scratch/outputs/MARA/manifests/plan5/ragtruth`.

Expected:

- short source-level documents can produce usable evidence,
- verifier does not reject supported final answer because Finance numeric heuristics are absent,
- unsupported labels remain measurable as verifier diagnostics.

- [ ] **Step 4: Run ALCE readiness**

Use the ALCE manifest generated under `~/scratch/outputs/MARA/manifests/plan5/alce`.

Expected:

- source-level citation recall/precision is populated,
- answer scoring uses cleaned final answer,
- route diagnostics have no unclassified failures.

- [ ] **Step 5: Check artifacts**

For each output directory:

```bash
test -s summary.json
test -s predictions.jsonl
rg '<think>|base64|data:image' predictions.jsonl
```

Expected: first two commands pass; `rg` returns no matches for verifier/scorer-visible fields.

### Task 12: Run 10-Sample Regression Matrix

**Files:**

- No repository files should change in this task.
- Slurm scripts and outputs must stay in `~/scratch/outputs/MARA/slurm` and `~/scratch/outputs/MARA/artifacts`.

- [ ] **Step 1: Submit serialized Slurm jobs**

Avoid same-node port collisions by chaining jobs or assigning unique ports and app data dirs per job.

```bash
sbatch --parsable ~/scratch/outputs/MARA/slurm/scripts/plan5_cross_dataset_10sample.sh financebench
sbatch --dependency=afterok:<finance_job_id> --parsable ~/scratch/outputs/MARA/slurm/scripts/plan5_cross_dataset_10sample.sh qasper
sbatch --dependency=afterok:<qasper_job_id> --parsable ~/scratch/outputs/MARA/slurm/scripts/plan5_cross_dataset_10sample.sh ragtruth
sbatch --dependency=afterok:<ragtruth_job_id> --parsable ~/scratch/outputs/MARA/slurm/scripts/plan5_cross_dataset_10sample.sh alce
```

- [ ] **Step 2: Validate job completion**

```bash
sacct -j <job_ids> --format=JobID,JobName,State,ExitCode,Elapsed,NodeList
```

Expected: each main job is `COMPLETED` with `ExitCode=0:0`.

- [ ] **Step 3: Validate result invariants**

For each artifact:

```bash
python scripts/inspect_benchmark_artifact.py <artifact_dir>
```

Expected:

- zero execution errors,
- zero skipped required routes,
- no image payload in text routes,
- no `<think>` in verifier/scorer inputs,
- diagnostics populated for remaining misses.

- [ ] **Step 4: Compare against previous run**

Compare:

- retrieval source hit,
- page/locator hit where applicable,
- citation precision/recall by locator kind,
- verifier abstention and false abstention,
- controller route switch rate,
- answer F1/EM as secondary outcome.

Expected: no dataset should regress because of a fix aimed at another dataset. A score regression is acceptable only when diagnostics show stricter, more correct behavior.

### Task 13: Run Hygiene And Targeted Gates

**Files:**

- All changed Python files.

- [ ] **Step 1: Run hygiene gate**

```bash
uv run --python 3.10 python scripts/check_codebase_hygiene.py \
  benchmark/dataset_profiles.py \
  benchmark/evidence_adapters.py \
  benchmark/page_alignment.py \
  benchmark/citation_metrics.py \
  benchmark/diagnostics.py \
  benchmark/scoring.py \
  benchmark/summary.py \
  benchmark/reports.py \
  benchmark/manifest.py \
  benchmark/manifest_templates.py \
  benchmark/docqa_evidence_projection.py \
  benchmark/docqa_runtime_sources.py \
  benchmark/engines.py \
  libs/ktem/ktem/docqa/evidence_text.py \
  libs/ktem/ktem/docqa/verification.py \
  libs/ktem/ktem/docqa/domain_verifiers.py \
  libs/ktem/ktem/reasoning/mara_route_retrieval.py \
  libs/ktem/ktem/reasoning/mara_controller.py
```

Expected: no new hygiene violations; do not refresh the baseline.

- [ ] **Step 2: Run pre-commit on changed files**

```bash
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

Expected: pass.

- [ ] **Step 3: Run focused benchmark tests**

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_no_finance_specialization_boundaries.py \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_docqa_runtime_engine_sources.py \
  benchmark/tests/test_scoring.py \
  benchmark/tests/test_manifest_templates.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  -q
```

Expected: pass.

- [ ] **Step 4: Run focused ktem tests**

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  libs/ktem/ktem_tests/test_mara_retrieval_quality.py \
  -q
```

Expected: pass.

### Task 14: Readiness Decision For Formal Plan(5) Runs

**Files:**

- No code files should change in this task.
- Update only benchmark reports or a run log under `~/scratch/outputs/MARA`.

- [ ] **Step 1: Check formal-run blockers**

Proceed only if all are true:

- storage layout passes,
- hygiene and pre-commit pass,
- targeted tests pass,
- 1-sample matrix has zero execution errors,
- 10-sample matrix has zero execution errors,
- verifier/scorer do not consume `<think>` text,
- text routes do not pass image payloads to text LLM,
- every remaining low-score bucket maps to the shared taxonomy.

- [ ] **Step 2: Record residual risk**

Write a short run note covering:

- datasets where retrieval quality remains weak,
- datasets where citation matching remains proxy-level,
- controller routes that need larger-sample validation,
- whether a domain verifier was disabled or explicitly configured.

- [ ] **Step 3: Submit formal Plan(5) jobs**

Use the Plan(5) phase order:

1. FinanceBench and QASPER text main experiment,
2. RAGTruth guardrail experiment,
3. ALCE citation experiment,
4. multimodal datasets after text capability gates remain stable.

Expected: formal runs start only after generic capability behavior is stable across all four text datasets.

---

## Acceptance Criteria

The implementation is ready for formal Plan(5) benchmark runs when:

- Generic runtime/scoring/controller modules do not import FinanceBench-specific adapters.
- FinanceBench, QASPER, RAGTruth, and ALCE all run through the same evidence/citation/verifier/controller interfaces.
- Dataset differences are represented by capability profiles and normalized evidence records.
- FinanceBench page alignment is improved without making page labels mandatory for source-level datasets.
- RAGTruth and ALCE source-level citations work without page-specific hacks.
- Verifier/scorer use cleaned final answers and ignore model thinking traces.
- Controller route choices are limited by profile-derived `allowed_routes`.
- Diagnostic reports explain remaining failures by shared taxonomy.
- Storage, hygiene, pre-commit, targeted tests, and 1-sample/10-sample matrix gates pass.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-15-generic-cross-dataset-benchmark-capabilities.md`.

Recommended execution order:

1. Subagent-driven execution for Tasks 1-10, one task at a time with review checkpoints.
2. Inline execution for Tasks 11-14 because they depend on the local Slurm/runtime environment.
