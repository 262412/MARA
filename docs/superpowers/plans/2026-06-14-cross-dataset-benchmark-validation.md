# Cross-Dataset Benchmark Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate MARA retrieval, evidence, citation, verifier, and controller behavior across FinanceBench, QASPER, RAGTruth, ALCE, and later multimodal datasets without adding Finance-specific control flow.

**Architecture:** Treat every benchmark as a dataset capability profile plus normalized evidence records. Route templates, evaluators, verifier cleanup, retrieval diagnostics, and controller allowed-route policy consume those generic capabilities instead of branching on FinanceBench names.

**Tech Stack:** Python 3.10, existing `benchmark` package, `ktem.docqa` verification utilities, MARA DocQA runtime, JSON schema v2 manifests, pytest, `scripts/check_codebase_hygiene.py`, pre-commit.

---

## Public Surface And Boundaries

Affected public surfaces:

- Benchmark CLI: `python -m benchmark normalize-*`, `apply-route-template`, and `run`.
- Manifest JSON keys: `documents`, `examples`, `routes`, `gold_evidence`, `metadata`, route-level backend fields.
- Report JSON/CSV/Markdown keys: retrieval diagnostics, citation metrics, verifier metrics, controller route metrics.
- DocQA runtime behavior exposed through benchmark: cleaned final answer, citation mode, claim verification, controller route selection.
- Controller route policy: allowed route list and route-switch behavior for text-only versus multimodal profiles.

Not allowed:

- No new Finance-only verifier, scorer, retriever, or controller branch.
- No benchmark readiness signal based on root `pytest -q`.
- No generated datasets, indexes, logs, model cache, or runtime state inside the repository.
- No `scripts/codebase_hygiene_baseline.json` refresh to pass checks.

Storage preflight required before running `uv`, model calls, DocQA indexing, dataset sync, or Slurm:

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

- `.venv` resolves to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Caches and `KH_APP_DATA_DIR` resolve to `~/fastscratch`, except `PRE_COMMIT_HOME` under `~/scratch/pre-commit-cache`.
- `fastscratch`, `scratch`, and `data` are below soft quota.
- No `data`, `datasets`, or `outputs` directory exists under the repo root.

---

## File Structure

- Create `benchmark/dataset_profiles.py`: generic dataset capability profiles, not dataset-specific execution logic.
- Modify `benchmark/manifest.py`: attach derived profile metadata to manifest bundles without changing stored manifest keys.
- Modify `benchmark/manifest_templates.py`: keep route-template composition generic.
- Modify `benchmark/evidence_adapters.py`: normalize gold evidence from page, span, source, citation, hallucination, and multimodal shapes.
- Modify `benchmark/page_alignment.py`: align gold page labels to parser pages generically.
- Modify `benchmark/scoring.py`: consume normalized evidence and cleaned final answer for scoring.
- Modify `benchmark/verification_metrics.py`: report verifier and unsupported-claim metrics across datasets.
- Modify `benchmark/research_adapters.py`: label proxy versus paper-grade metrics for QASPER/RAGTruth/ALCE without changing runtime logic.
- Modify `benchmark/diagnostics.py`: classify retrieval and evidence failures independent of dataset name.
- Modify `benchmark/reports.py` and `benchmark/summary.py`: expose route-level diagnostics and profile-level metrics.
- Modify `benchmark/manifests/templates/*.json`: express route policy by data shape, not FinanceBench.
- Modify `libs/ktem/ktem/docqa/claim_filtering.py` or existing verification cleaner: strip model thinking text before verifier/scorer.
- Modify `libs/ktem/ktem/reasoning/mara_route_retrieval.py`: prevent hybrid/controller from invoking visual/page-image paths unless the route profile enables them.
- Test under `benchmark/tests/` and `libs/ktem/ktem_tests/`.
- Update `benchmark/README.md` with route-template and cross-dataset run commands.

---

### Task 1: Add Dataset Capability Profiles

**Files:**

- Create: `benchmark/dataset_profiles.py`
- Modify: `benchmark/manifest.py`
- Test: `benchmark/tests/test_dataset_profiles.py`

- [ ] **Step 1: Write failing tests for generic profiles**

Create `benchmark/tests/test_dataset_profiles.py`:

```python
from benchmark.dataset_profiles import (
    DatasetCapabilities,
    profile_for_manifest,
)


def test_financebench_profile_is_page_grounded_not_special_controller_logic():
    profile = profile_for_manifest("financebench_plan5_text_main", examples=[])

    assert profile.dataset_family == "financebench"
    assert profile.capabilities == DatasetCapabilities(
        answer_correctness=True,
        page_evidence=True,
        span_evidence=True,
        citation_quality=True,
        hallucination_labels=False,
        multi_document=False,
        multimodal=False,
    )
    assert profile.allowed_text_routes == ("doc_text", "hybrid", "graph_global")


def test_qasper_profile_supports_span_and_multidoc_text_evidence():
    profile = profile_for_manifest("qasper_plan5_text_main", examples=[])

    assert profile.dataset_family == "qasper"
    assert profile.capabilities.span_evidence is True
    assert profile.capabilities.multi_document is True
    assert profile.capabilities.hallucination_labels is False


def test_ragtruth_profile_supports_hallucination_labels():
    profile = profile_for_manifest("ragtruth_plan5_guardrail", examples=[])

    assert profile.dataset_family == "ragtruth"
    assert profile.capabilities.hallucination_labels is True
    assert profile.capabilities.citation_quality is False


def test_alce_profile_supports_citation_quality():
    profile = profile_for_manifest("alce_plan5_citation", examples=[])

    assert profile.dataset_family == "alce"
    assert profile.capabilities.citation_quality is True
    assert profile.capabilities.page_evidence is False
```

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_dataset_profiles.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'benchmark.dataset_profiles'
```

- [ ] **Step 3: Implement profile definitions**

Create `benchmark/dataset_profiles.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DatasetCapabilities:
    answer_correctness: bool
    page_evidence: bool
    span_evidence: bool
    citation_quality: bool
    hallucination_labels: bool
    multi_document: bool
    multimodal: bool


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    dataset_family: str
    capabilities: DatasetCapabilities
    allowed_text_routes: tuple[str, ...]
    allowed_multimodal_routes: tuple[str, ...]


TEXT_ROUTES = ("doc_text", "hybrid", "graph_global")
MULTIMODAL_ROUTES = (
    "doc_text",
    "hybrid",
    "doc_page_image",
    "doc_element",
    "graph_global",
)


def profile_for_manifest(dataset_name: str, *, examples: Iterable[object]) -> DatasetProfile:
    family = _dataset_family(dataset_name)
    inferred_multidoc = any(bool(getattr(item, "document_ids", [])) for item in examples)
    if family == "ragtruth":
        return DatasetProfile(
            dataset_family=family,
            capabilities=DatasetCapabilities(
                answer_correctness=False,
                page_evidence=False,
                span_evidence=True,
                citation_quality=False,
                hallucination_labels=True,
                multi_document=inferred_multidoc,
                multimodal=False,
            ),
            allowed_text_routes=TEXT_ROUTES,
            allowed_multimodal_routes=MULTIMODAL_ROUTES,
        )
    if family == "alce":
        return DatasetProfile(
            dataset_family=family,
            capabilities=DatasetCapabilities(
                answer_correctness=True,
                page_evidence=False,
                span_evidence=True,
                citation_quality=True,
                hallucination_labels=False,
                multi_document=True,
                multimodal=False,
            ),
            allowed_text_routes=TEXT_ROUTES,
            allowed_multimodal_routes=MULTIMODAL_ROUTES,
        )
    if family == "qasper":
        return DatasetProfile(
            dataset_family=family,
            capabilities=DatasetCapabilities(
                answer_correctness=True,
                page_evidence=False,
                span_evidence=True,
                citation_quality=True,
                hallucination_labels=False,
                multi_document=True,
                multimodal=False,
            ),
            allowed_text_routes=TEXT_ROUTES,
            allowed_multimodal_routes=MULTIMODAL_ROUTES,
        )
    if family in {"mmdocrag", "slidevqa", "vidore"}:
        return DatasetProfile(
            dataset_family=family,
            capabilities=DatasetCapabilities(
                answer_correctness=True,
                page_evidence=True,
                span_evidence=True,
                citation_quality=True,
                hallucination_labels=False,
                multi_document=inferred_multidoc,
                multimodal=True,
            ),
            allowed_text_routes=TEXT_ROUTES,
            allowed_multimodal_routes=MULTIMODAL_ROUTES,
        )
    return DatasetProfile(
        dataset_family=family,
        capabilities=DatasetCapabilities(
            answer_correctness=True,
            page_evidence=True,
            span_evidence=True,
            citation_quality=True,
            hallucination_labels=False,
            multi_document=inferred_multidoc,
            multimodal=False,
        ),
        allowed_text_routes=TEXT_ROUTES,
        allowed_multimodal_routes=MULTIMODAL_ROUTES,
    )


def _dataset_family(dataset_name: str) -> str:
    value = str(dataset_name or "").strip().lower()
    for family in ("financebench", "qasper", "ragtruth", "alce", "mmdocrag", "slidevqa", "vidore"):
        if family in value:
            return family
    return value or "unknown"
```

- [ ] **Step 4: Attach profiles in manifest loading**

Modify `benchmark/manifest.py` so `load_manifest()` derives a profile after examples are parsed:

```python
from .dataset_profiles import profile_for_manifest

# after ManifestBundle is created:
bundle.metadata = {
    "dataset_profile": profile_for_manifest(
        bundle.dataset_name,
        examples=bundle.examples,
    )
}
```

If `ManifestBundle` does not currently carry metadata, add `metadata: dict[str, Any] = field(default_factory=dict)` to `benchmark/schemas.py` with tests that serialization remains stable.

- [ ] **Step 5: Run profile tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_dataset_profiles.py -q
```

Expected:

```text
4 passed
```

---

### Task 2: Make Route Templates Data-Shape Driven

**Files:**

- Modify: `benchmark/manifests/templates/mara_text_only.json`
- Modify: `benchmark/manifests/templates/mara_multimodal.json`
- Modify: `benchmark/manifests/templates/mara_all_routes.local.json`
- Modify: `benchmark/manifests/templates/mara_financebench_text.json`
- Test: `benchmark/tests/test_manifest_adapter_boundaries.py`

- [ ] **Step 1: Write failing tests that reject text-template visual backends**

Add to `benchmark/tests/test_manifest_adapter_boundaries.py`:

```python
from benchmark.manifest import load_manifest


def test_text_templates_do_not_enable_visual_backends():
    for template in (
        "benchmark/manifests/templates/mara_text_only.json",
        "benchmark/manifests/templates/mara_financebench_text.json",
    ):
        bundle = load_manifest(template)
        for route in bundle.routes:
            assert "visual_retriever_backend" not in route
            assert "visual_generator_backend" not in route
            assert "visual_backend_type" not in route


def test_multimodal_template_keeps_visual_routes_explicit():
    bundle = load_manifest("benchmark/manifests/templates/mara_multimodal.json")
    route_by_id = {route["route_id"]: route for route in bundle.routes}

    assert route_by_id["page_image_rag_vlm"]["route_policy"] == "visual"
    assert route_by_id["controller_auto"]["allowed_routes"] == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]
```

- [ ] **Step 2: Run tests and confirm RED if templates still enable visual paths**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_manifest_adapter_boundaries.py::test_text_templates_do_not_enable_visual_backends benchmark/tests/test_manifest_adapter_boundaries.py::test_multimodal_template_keeps_visual_routes_explicit -q
```

Expected if stale template fields remain:

```text
FAILED ... assert 'visual_retriever_backend' not in route
```

- [ ] **Step 3: Update templates**

Use these route-policy rules:

- Text-only and FinanceBench text templates:
  - no `visual_*` keys
  - `controller_auto.allowed_routes = ["doc_text", "hybrid", "graph_global"]`
  - `crag_guarded.allowed_routes = ["doc_text", "hybrid", "graph_global"]`
- Multimodal templates:
  - keep visual routes explicit
  - keep visual backend metadata only on visual routes
- All-routes smoke template:

  - keep every route, but mark unavailable backend routes with `requires_backend_config` and skipped-route metadata.

- [ ] **Step 4: Run template tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_manifest.py::test_manifest_templates_load_expected_mara_route_sets benchmark/tests/test_manifest_adapter_boundaries.py -q
```

Expected:

```text
passed
```

---

### Task 3: Normalize Evidence Across Dataset Shapes

**Files:**

- Modify: `benchmark/evidence_adapters.py`
- Modify: `benchmark/scoring.py`
- Test: `benchmark/tests/test_evidence_adapters.py`

- [ ] **Step 1: Write failing tests for normalized evidence**

Create `benchmark/tests/test_evidence_adapters.py`:

```python
from benchmark.evidence_adapters import normalize_gold_evidence
from benchmark.schemas import BenchmarkExample


def _example(**overrides):
    payload = {
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
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_evidence_adapters.py -q
```

Expected:

```text
ImportError or AttributeError for normalize_gold_evidence / normalized fields
```

- [ ] **Step 3: Implement normalized evidence dataclass**

In `benchmark/evidence_adapters.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def normalize_gold_evidence(example: Any) -> list[NormalizedEvidence]:
    rows = list(getattr(example, "gold_evidence", []) or [])
    pages = list(getattr(example, "evidence_pages", []) or [])
    sources = list(getattr(example, "evidence_sources", []) or [])
    if not rows:
        rows = [{} for _ in range(max(len(pages), len(sources), 1))]
    normalized: list[NormalizedEvidence] = []
    for index, row in enumerate(rows):
        source = _first_text(row, "source", "citation", "id")
        if not source and index < len(sources):
            source = str(sources[index])
        page_label = _page_label(row)
        if page_label is None and index < len(pages):
            page_label = str(pages[index])
        normalized.append(
            NormalizedEvidence(
                document_id=_first_text(row, "document_id", "doc_id"),
                page_label=page_label,
                page_index=_page_index(row),
                source=source,
                span_text=_first_text(row, "text", "span", "quote", "evidence"),
                element_id=_first_text(row, "element_id", "element"),
                modality=_first_text(row, "modality", "type"),
                support_label=_first_text(row, "label", "support_label", "verdict"),
            )
        )
    return normalized


def _first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _page_label(row: dict[str, Any]) -> str | None:
    value = row.get("page_label", row.get("page"))
    if value in (None, ""):
        return None
    return str(value)


def _page_index(row: dict[str, Any]) -> int | None:
    value = row.get("page_index")
    if value in (None, ""):
        return None
    return int(value)
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_evidence_adapters.py -q
```

Expected:

```text
4 passed
```

---

### Task 4: Make Page Alignment Generic

**Files:**

- Modify: `benchmark/page_alignment.py`
- Modify: `benchmark/financebench_pages.py` only to call generic helpers if still needed
- Test: `benchmark/tests/test_page_alignment.py`

- [ ] **Step 1: Write failing tests for page labels and parser pages**

Create `benchmark/tests/test_page_alignment.py`:

```python
from benchmark.page_alignment import align_gold_page


def test_aligns_numeric_gold_page_to_parser_page_label():
    parser_pages = [
        {"page_index": 0, "page_label": "i"},
        {"page_index": 1, "page_label": "1"},
        {"page_index": 2, "page_label": "2"},
    ]

    assert align_gold_page("2", parser_pages) == 2


def test_aligns_one_based_gold_page_when_labels_are_missing():
    parser_pages = [{"page_index": 0}, {"page_index": 1}, {"page_index": 2}]

    assert align_gold_page(2, parser_pages) == 1


def test_returns_none_for_unaligned_gold_page():
    parser_pages = [{"page_index": 0, "page_label": "A-1"}]

    assert align_gold_page("99", parser_pages) is None
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_page_alignment.py -q
```

Expected:

```text
ImportError or assertion failure for align_gold_page
```

- [ ] **Step 3: Implement alignment helper**

In `benchmark/page_alignment.py`:

```python
from __future__ import annotations

from typing import Any


def align_gold_page(gold_page: int | str, parser_pages: list[dict[str, Any]]) -> int | None:
    gold = str(gold_page).strip()
    if not gold:
        return None
    for page in parser_pages:
        label = str(page.get("page_label") or "").strip()
        if label and label == gold:
            return int(page["page_index"])
    if gold.isdigit():
        one_based = int(gold) - 1
        for page in parser_pages:
            if int(page.get("page_index", -1)) == one_based:
                return one_based
    return None
```

- [ ] **Step 4: Remove Finance-only page scoring branches**

Replace direct Finance page-offset logic with calls to `align_gold_page()`. Keep Finance-specific parsing only in a converter if the source dataset stores unique metadata that must be converted into generic `page_label` or `gold_evidence`.

- [ ] **Step 5: Run page alignment and Finance page tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_page_alignment.py benchmark/tests/test_financebench_pages.py -q
```

Expected:

```text
passed
```

---

### Task 5: Add Retrieval And Evidence Failure Diagnostics

**Files:**

- Modify: `benchmark/diagnostics.py`
- Modify: `benchmark/runner.py`
- Modify: `benchmark/reports.py`
- Test: `benchmark/tests/test_runner_diagnostics.py`

- [ ] **Step 1: Write failing diagnostic tests**

Add to `benchmark/tests/test_runner_diagnostics.py`:

```python
from benchmark.diagnostics import prediction_diagnostics


def test_diagnoses_raw_retriever_zero():
    prediction = {
        "retrieved_hits": [],
        "retrieval_trace": [{"stage": "raw_retriever", "count": 0}],
        "gold_pages": [3],
        "predicted_pages": [],
        "predicted_sources": [],
    }

    diagnostics = prediction_diagnostics(prediction)

    assert diagnostics["retrieval_failure_type"] == "raw_retriever_zero"


def test_diagnoses_wrong_page_after_nonzero_retrieval():
    prediction = {
        "retrieved_hits": [{"page": 9, "source": "doc.pdf#page:9"}],
        "retrieval_trace": [{"stage": "raw_retriever", "count": 5}],
        "gold_pages": [3],
        "predicted_pages": [9],
        "predicted_sources": ["doc.pdf#page:9"],
    }

    diagnostics = prediction_diagnostics(prediction)

    assert diagnostics["retrieval_failure_type"] == "wrong_page"
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_runner_diagnostics.py -q
```

Expected:

```text
FAILED ... KeyError or unexpected retrieval_failure_type
```

- [ ] **Step 3: Implement generic diagnostic categories**

In `benchmark/diagnostics.py`, classify only from generic prediction fields:

```python
def _retrieval_failure_type(prediction: dict[str, object]) -> str:
    if not prediction.get("retrieved_hits"):
        raw_counts = [
            int(row.get("count", 0) or 0)
            for row in prediction.get("retrieval_trace", [])
            if isinstance(row, dict) and row.get("stage") == "raw_retriever"
        ]
        if raw_counts and max(raw_counts) == 0:
            return "raw_retriever_zero"
        return "no_retrieved_hits"
    gold_pages = {str(item) for item in prediction.get("gold_pages", [])}
    predicted_pages = {str(item) for item in prediction.get("predicted_pages", [])}
    if gold_pages and predicted_pages and gold_pages.isdisjoint(predicted_pages):
        return "wrong_page"
    if gold_pages and not predicted_pages:
        return "missing_page_metadata"
    if prediction.get("predicted_sources") == []:
        return "missing_citation_metadata"
    return "none"
```

- [ ] **Step 4: Attach diagnostics to predictions and reports**

In `benchmark/runner.py`, after scoring and before appending each prediction:

```python
prediction["diagnostics"] = prediction_diagnostics(prediction)
```

In `benchmark/reports.py`, include `diagnostics.retrieval_failure_type` in route metrics and error tables.

- [ ] **Step 5: Run diagnostics tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_runner_diagnostics.py benchmark/tests/test_reports_diagnostics.py -q
```

Expected:

```text
passed
```

---

### Task 6: Strip Thinking Text Before Scoring And Verification

**Files:**

- Modify: `libs/ktem/ktem/docqa/claim_filtering.py` or the existing answer-cleaning helper
- Modify: `benchmark/scoring.py`
- Modify: `libs/ktem/ktem/docqa/verification.py`
- Test: `benchmark/tests/test_scoring.py`
- Test: `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`

- [ ] **Step 1: Write failing scoring test**

Add to `benchmark/tests/test_scoring.py`:

```python
from benchmark.scoring import score_prediction


def test_scoring_uses_final_answer_after_thinking_text():
    prediction = {
        "gold_answers": ["42"],
        "predicted_answer": "<think>Need to calculate carefully.</think>\nFinal answer: 42",
        "predicted_pages": [],
        "gold_pages": [],
        "predicted_sources": [],
        "gold_sources": [],
        "expected_formats": [],
        "expected_guardrails": {},
        "gold_evidence": [],
        "claim_verification": {},
    }

    metrics = score_prediction(prediction)

    assert metrics["em"] == 1.0
```

- [ ] **Step 2: Write failing verifier test**

Add to `libs/ktem/ktem_tests/test_docqa_verification_regressions.py`:

```python
from ktem.docqa.claim_filtering import clean_answer_text


def test_clean_answer_text_removes_qwen_thinking_block():
    answer = "<think>The evidence says this should be 42.</think>\nFinal answer: 42"

    assert clean_answer_text(answer) == "42"
```

- [ ] **Step 3: Run tests and confirm RED**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_scoring.py::test_scoring_uses_final_answer_after_thinking_text libs/ktem/ktem_tests/test_docqa_verification_regressions.py::test_clean_answer_text_removes_qwen_thinking_block -q
```

Expected:

```text
FAILED ... thinking text remains in answer
```

- [ ] **Step 4: Implement generic final-answer cleaning**

In the shared cleaner:

```python
import re

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_FINAL_PREFIX_RE = re.compile(r"^\s*(final answer|answer)\s*:\s*", re.IGNORECASE)


def clean_answer_text(answer: str) -> str:
    text = _THINK_BLOCK_RE.sub("", str(answer or "")).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        text = lines[-1] if any(_FINAL_PREFIX_RE.match(line) for line in lines) else "\n".join(lines)
    return _FINAL_PREFIX_RE.sub("", text).strip()
```

Keep the existing cleaner behavior if the function already exists; add only the missing generic stripping cases.

- [ ] **Step 5: Run scoring and verifier tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_scoring.py libs/ktem/ktem_tests/test_docqa_verification_regressions.py -q
```

Expected:

```text
passed
```

---

### Task 7: Gate Hybrid And Controller Visual Paths By Route Capability

**Files:**

- Modify: `libs/ktem/ktem/reasoning/mara_route_retrieval.py`
- Modify: route templates if needed
- Test: `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`

- [ ] **Step 1: Write failing test that text hybrid does not build page-image metadata**

Add to `libs/ktem/ktem_tests/test_mara_controller_route_extensions.py`:

```python
import pytest

from kotaemon.base import RetrievedDocument
from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning import mara_route_retrieval as route_retrieval


def test_hybrid_route_skips_page_image_metadata_without_visual_backend(monkeypatch):
    def fail_page_image_build(*args, **kwargs):
        raise AssertionError("text hybrid route must not build page-image records")

    monkeypatch.setattr(route_retrieval, "build_local_page_image_records", fail_page_image_build)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.selected_file_records = [{"file_id": "doc-1", "path": "doc.pdf"}]

    docs = [
        RetrievedDocument(
            text="Revenue increased.",
            id_="chunk-1",
            metadata={"file_id": "doc-1", "page_label": "3"},
        )
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "hybrid_rag",
        docs,
        [],
        pipeline.build_evidence_metadata,
    )

    assert "page_image_index" not in metadata
```

- [ ] **Step 2: Write passing-path test for explicit visual backend**

Add:

```python
def test_hybrid_route_includes_page_image_metadata_when_visual_backend_is_configured():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.visual_retriever_backend = "local_late_interaction"
    pipeline.page_image_index_records = [
        {
            "evidence_id": "page-image:doc-1:3",
            "file_id": "doc-1",
            "page_label": "3",
            "image_path": "/scratch/page-3.png",
        }
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "hybrid_rag",
        [],
        [],
        pipeline.build_evidence_metadata,
    )

    assert metadata["page_image_index"][0]["evidence_id"] == "page-image:doc-1:3"
```

- [ ] **Step 3: Run tests and confirm RED**

Run:

```bash
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_mara_controller_route_extensions.py::test_hybrid_route_skips_page_image_metadata_without_visual_backend libs/ktem/ktem_tests/test_mara_controller_route_extensions.py::test_hybrid_route_includes_page_image_metadata_when_visual_backend_is_configured -q
```

Expected:

```text
FAILED ... text hybrid route must not build page-image records
```

- [ ] **Step 4: Implement generic visual capability gating**

In `libs/ktem/ktem/reasoning/mara_route_retrieval.py`:

```python
def _page_image_metadata_enabled(pipeline: object) -> bool:
    return bool(
        getattr(pipeline, "visual_retriever", None)
        or getattr(pipeline, "visual_retriever_backend", None)
        or getattr(pipeline, "page_image_index_records", None)
    )


def _hybrid_page_image_metadata(pipeline: object) -> dict[str, object]:
    if not _page_image_metadata_enabled(pipeline):
        return {}
    return _page_image_metadata(pipeline)
```

Use `_hybrid_page_image_metadata()` in the `hybrid_rag` branch instead of calling `_page_image_metadata()` unconditionally.

- [ ] **Step 5: Run controller route tests**

Run:

```bash
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_mara_controller_route_extensions.py -q
```

Expected:

```text
passed
```

---

### Task 8: Make Citation Metrics Dataset-Neutral

**Files:**

- Modify: `benchmark/scoring.py`
- Modify: `benchmark/metrics.py` only if citation helpers are incomplete
- Modify: `benchmark/research_adapters.py`
- Test: `benchmark/tests/test_research_evaluators.py`
- Test: `benchmark/tests/test_scoring.py`

- [ ] **Step 1: Write tests for citation targets from ALCE and QASPER shapes**

Add to `benchmark/tests/test_scoring.py`:

```python
from benchmark.scoring import score_prediction


def test_citation_precision_recall_use_gold_evidence_sources():
    prediction = {
        "gold_answers": ["The answer is attributable."],
        "predicted_answer": "The answer is attributable. [doc-a]",
        "predicted_pages": [],
        "gold_pages": [],
        "predicted_sources": ["doc-a"],
        "gold_sources": [],
        "expected_formats": [],
        "expected_guardrails": {},
        "gold_evidence": [{"citation": "doc-a", "text": "The answer is attributable."}],
        "claim_verification": {},
    }

    metrics = score_prediction(prediction)

    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0
```

- [ ] **Step 2: Run tests and confirm RED if source-only evidence is ignored**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_scoring.py::test_citation_precision_recall_use_gold_evidence_sources -q
```

Expected if current metrics ignore `gold_evidence[].citation`:

```text
FAILED ... assert None == 1.0
```

- [ ] **Step 3: Reuse normalized evidence in citation scoring**

Update citation scoring to extract sources through `normalize_gold_evidence()`. The scoring function should not check dataset name.

- [ ] **Step 4: Run scoring and research adapter tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_scoring.py benchmark/tests/test_research_evaluators.py -q
```

Expected:

```text
passed
```

---

### Task 9: Keep Verifier Metrics Generic And Label Proxy Metrics

**Files:**

- Modify: `benchmark/verification_metrics.py`
- Modify: `benchmark/research_adapters.py`
- Modify: `benchmark/reports.py`
- Test: `benchmark/tests/test_research_evaluators.py`
- Test: `benchmark/tests/test_reports_diagnostics.py`

- [ ] **Step 1: Write tests for metric metadata**

Add to `benchmark/tests/test_research_evaluators.py`:

```python
from benchmark.research_adapters import research_adapter_metric_metadata


def test_research_adapter_metadata_marks_proxy_metrics():
    metadata = research_adapter_metric_metadata()

    assert metadata["ragtruth"]["metric_scope"] == "proxy"
    assert metadata["alce"]["paper_grade"] is False
    assert "paper-grade citation evaluator or judge" in metadata["alce"]["requires_external_resources"]
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_research_evaluators.py::test_research_adapter_metadata_marks_proxy_metrics -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Ensure reports expose proxy labels**

In `benchmark/reports.py`, include evaluator metadata in `summary.json` and `report.md`:

```python
summary["research_metric_metadata"] = research_adapter_metric_metadata()
```

The report should state proxy metrics are not paper-grade when external evaluators are not configured.

- [ ] **Step 4: Run report diagnostic tests**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests/test_reports_diagnostics.py -q
```

Expected:

```text
passed
```

---

### Task 10: Materialize Cross-Dataset Manifests With The Same Route Policy

**Files:**

- Modify: `benchmark/README.md`
- No repository dataset outputs; write generated manifests to `~/scratch/outputs/MARA/manifests/plan5/`

- [ ] **Step 1: Generate or refresh base manifests**

Run only after storage preflight passes:

```bash
mkdir -p ~/scratch/outputs/MARA/manifests/plan5/{financebench,qasper,ragtruth,alce}

uv run --python 3.10 python -m benchmark normalize-financebench \
  --source-dir ~/scratch/datasets/MARA/financebench \
  --output ~/scratch/outputs/MARA/manifests/plan5/financebench/financebench.base.json

uv run --python 3.10 python -m benchmark normalize-qasper \
  --source ~/scratch/datasets/MARA/qasper/raw/qasper-dev-v0.3.json \
  --output ~/scratch/outputs/MARA/manifests/plan5/qasper/qasper-dev.base.json

uv run --python 3.10 python -m benchmark normalize-ragtruth \
  --source-info ~/scratch/datasets/MARA/ragtruth/dataset/source_info.jsonl \
  --responses ~/scratch/datasets/MARA/ragtruth/dataset/response.jsonl \
  --output ~/scratch/outputs/MARA/manifests/plan5/ragtruth/ragtruth.base.json

uv run --python 3.10 python -m benchmark normalize-alce \
  --source ~/data/datasets/MARA/alce/data/asqa_eval_gtr_top100.json \
  --output ~/scratch/outputs/MARA/manifests/plan5/alce/alce-asqa-gtr.base.json
```

Expected:

```text
Manifest written to ...
```

- [ ] **Step 2: Apply route templates**

Run:

```bash
uv run --python 3.10 python -m benchmark apply-route-template \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/financebench/financebench.base.json \
  --template benchmark/manifests/templates/mara_text_only.json \
  --dataset-name financebench_plan5_text_main \
  --output ~/scratch/outputs/MARA/manifests/plan5/financebench/financebench.text-main.routes.json

uv run --python 3.10 python -m benchmark apply-route-template \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/qasper/qasper-dev.base.json \
  --template benchmark/manifests/templates/mara_text_only.json \
  --dataset-name qasper_plan5_text_main \
  --output ~/scratch/outputs/MARA/manifests/plan5/qasper/qasper-dev.text-main.routes.json

uv run --python 3.10 python -m benchmark apply-route-template \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/ragtruth/ragtruth.base.json \
  --template benchmark/manifests/templates/mara_text_only.json \
  --dataset-name ragtruth_plan5_guardrail \
  --output ~/scratch/outputs/MARA/manifests/plan5/ragtruth/ragtruth.guardrail.routes.json

uv run --python 3.10 python -m benchmark apply-route-template \
  --manifest ~/scratch/outputs/MARA/manifests/plan5/alce/alce-asqa-gtr.base.json \
  --template benchmark/manifests/templates/mara_text_only.json \
  --dataset-name alce_plan5_citation \
  --output ~/scratch/outputs/MARA/manifests/plan5/alce/alce-asqa-gtr.citation.routes.json
```

Expected:

```text
Manifest written to ...
```

- [ ] **Step 3: Verify generated manifest route policy**

Run:

```bash
uv run --python 3.10 python - <<'PY'
from pathlib import Path
from benchmark.manifest import load_manifest

paths = [
    Path("~/scratch/outputs/MARA/manifests/plan5/financebench/financebench.text-main.routes.json").expanduser(),
    Path("~/scratch/outputs/MARA/manifests/plan5/qasper/qasper-dev.text-main.routes.json").expanduser(),
    Path("~/scratch/outputs/MARA/manifests/plan5/ragtruth/ragtruth.guardrail.routes.json").expanduser(),
    Path("~/scratch/outputs/MARA/manifests/plan5/alce/alce-asqa-gtr.citation.routes.json").expanduser(),
]
for path in paths:
    bundle = load_manifest(path)
    route_ids = [route["route_id"] for route in bundle.routes]
    print(bundle.dataset_name, len(bundle.examples), route_ids)
    for route in bundle.routes:
        if route["route_id"] in {"controller_auto", "crag_guarded"}:
            print(" ", route["route_id"], route.get("allowed_routes"))
PY
```

Expected:

```text
controller_auto ['doc_text', 'hybrid', 'graph_global']
crag_guarded ['doc_text', 'hybrid', 'graph_global']
```

---

### Task 11: Run 10-Sample Regression Before Any Larger Benchmark

**Files:**

- No code edits.
- Outputs under `~/scratch/outputs/MARA/artifacts`.

- [ ] **Step 1: Confirm runtime endpoints**

Run:

```bash
.venv/bin/MARA docqa doctor
curl -s http://127.0.0.1:8000/v1/models
curl -s http://127.0.0.1:8002/health
```

Expected:

```text
Status: OK
```

The model endpoint should list the active local model. The retrieval health endpoint should list embedding/reranker backend status.

- [ ] **Step 2: Run four 10-sample regressions**

Run:

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
    --engine docqa_runtime \
    --scope multi-document \
    --output-dir ~/scratch/outputs/MARA/artifacts \
    --cache-mode warm \
    --max-context-length 3000 \
    --llm-name Qwen/Qwen3-8B \
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

- [ ] **Step 3: Analyze regressions by route and diagnostic type**

Run:

```bash
uv run --python 3.10 python - <<'PY'
import json
from pathlib import Path

root = Path("~/scratch/outputs/MARA/artifacts").expanduser()
for summary_path in sorted(root.glob("*/summary.json"))[-8:]:
    summary = json.loads(summary_path.read_text())
    print(summary_path.parent.name)
    print(" dataset:", summary.get("dataset_name"))
    print(" route metrics:", summary.get("route_metrics", [])[:2])
    print(" skipped:", summary.get("skipped_routes", []))
    print(" diagnostics:", summary.get("diagnostic_counts", {}))
PY
```

Expected:

- No visual/page-image backend calls in text-only runs.
- `retrieval_failure_type` differentiates `raw_retriever_zero`, `wrong_page`, `missing_citation_metadata`, and verifier abstention.
- RAGTruth exposes unsupported/abstention trade-off.
- ALCE exposes citation proxy metrics and proxy disclaimer.

---

### Task 12: Verification Gates Before Claiming Ready

**Files:**

- All changed Python files and templates.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
uv run --python 3.10 python -m pytest \
  benchmark/tests/test_dataset_profiles.py \
  benchmark/tests/test_evidence_adapters.py \
  benchmark/tests/test_page_alignment.py \
  benchmark/tests/test_manifest.py::test_manifest_templates_load_expected_mara_route_sets \
  benchmark/tests/test_manifest_adapter_boundaries.py \
  benchmark/tests/test_runner_diagnostics.py \
  benchmark/tests/test_reports_diagnostics.py \
  benchmark/tests/test_research_evaluators.py \
  benchmark/tests/test_scoring.py \
  libs/ktem/ktem_tests/test_docqa_verification_regressions.py \
  libs/ktem/ktem_tests/test_mara_controller_route_extensions.py \
  -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run relevant package-level gates**

Run:

```bash
uv run --python 3.10 python -m pytest benchmark/tests -q
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_docqa_verification_regressions.py libs/ktem/ktem_tests/test_mara_controller_route_extensions.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run hygiene and pre-commit on changed files**

Run with the actual changed file list:

```bash
changed_files="$(git diff --name-only --diff-filter=ACMR)"
uv run --python 3.10 python scripts/check_codebase_hygiene.py $changed_files
uv run --python 3.10 python -m pre_commit run --files $changed_files
```

Expected:

```text
Codebase hygiene check passed
```

and pre-commit exits `0`.

- [ ] **Step 4: Final storage check**

Run:

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

Expected:

- `.venv` and Python still resolve to fastscratch.
- `ktem_app_data` still resolves under fastscratch runtime.
- quotas remain below soft limit.
- no repo-local data/output directories exist.

---

## Execution Order

1. Task 1: dataset capability profiles.
2. Task 2: route templates by data shape.
3. Task 3: normalized evidence.
4. Task 4: generic page alignment.
5. Task 6: final-answer cleanup before scorer/verifier.
6. Task 7: route capability gating for hybrid/controller.
7. Task 5: diagnostics once prediction fields are stable.
8. Task 8: citation metrics from normalized evidence.
9. Task 9: proxy metric metadata and reports.
10. Task 10: manifest materialization.
11. Task 11: 10-sample regression across FinanceBench, QASPER, RAGTruth, ALCE.
12. Task 12: verification gates.

This order fixes the architecture first, then scoring/verifier correctness, then reporting and runs. It also prevents a repeated failure mode where a text-only benchmark accidentally invokes page-image extraction or VLM paths.

## Stop Conditions

Pause and inspect before continuing if any of these happen:

- Any text-only run touches `doc_page_image`, VLM, ColQwen/ColPali, or page-image PDF extraction.
- A metric implementation checks `dataset_name == "financebench"` outside a converter or dataset profile test.
- A verifier consumes `<think>...</think>` text as answer content.
- `raw_retriever_zero` is mixed with `wrong_page` or `missing_citation_metadata` in reports.
- Proxy metrics are reported without `paper_grade: false`.
- `fastscratch` file quota exceeds soft limit.

## Definition Of Done

- The same route-template and evaluator code runs FinanceBench, QASPER, RAGTruth, and ALCE 10-sample regressions.
- Reports separate retrieval miss, evidence formatting miss, citation miss, verifier abstention, and controller route choice.
- FinanceBench-specific code exists only in dataset conversion or source metadata normalization.
- Controller and hybrid route behavior is governed by route capabilities and allowed routes, not by FinanceBench assumptions.
- Scorer and verifier evaluate the final answer after stripping thinking text.
- All validation gates in Task 12 pass without refreshing `scripts/codebase_hygiene_baseline.json`.
