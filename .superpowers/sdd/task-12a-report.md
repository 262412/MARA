# Task 12A Report: Typed Preview Source and Office Conversion Core

## Outcome

Task 12A is implemented on top of base
`0a2002f8edb2991e536e2b6d7f373ce59bf88886`. The implementation commit is
`54b616a`.

The Web and DocQA Office preview paths now re-export one no-Gradio compatibility
service backed by a strict shared core. The core validates source signatures,
enforces bounded OOXML archive limits, coalesces same-source conversion, bounds
cross-source conversion concurrency, uses isolated LibreOffice output/profile
directories, validates PDF output, and publishes cache entries atomically.

Task 12B/12C work was intentionally not included: indexing/acceptance
integration, authorization, DOCX renderer decomposition, render/browser safety,
and Gradio event wiring remain deferred.

## Storage and Runtime Preflight

- Worktree: `/mnt/scratch/users/tbczhang/projects/MARA-quality-hardening`
- `.venv`: symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`
- Python: `/mnt/fastscratch/users/tbczhang/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10`
- Cache/runtime variables: uv and MARA runtime on fastscratch;
  `PRE_COMMIT_HOME=/users/tbczhang/scratch/pre-commit-cache`
- Repository-root `data/`, `datasets/`, and `outputs/`: absent
- Final fastscratch quota: 295.8G/500G soft; 471,856/500,000 soft files
- Final scratch quota: 71.91G/2T; 472,413/300,000 soft files and
  500,000 hard files, with grace active
- Every pytest command used a freshly created temporary `KH_APP_DATA_DIR` under
  `$MARA_RUNTIME_DIR`; the new tests also replace `KH_APP_DATA_DIR` with their
  own `tmp_path` fixture.

The scratch file quota was already over its soft limit at preflight. Initial
changed-file pre-commit setup installed missing hook environments and increased
scratch file use from 461,546 to 472,413. No caches or user data were deleted.

## Public Surface and Compatibility

- `MARA` and `MARA-cli`: no command, option, import, or dispatch changes.
- Web import preserved:
  `ktem.pages.chat.page_preview_office.OfficePreviewConversionService`.
- DocQA import preserved:
  `ktem.docqa.preview_support.OfficePreviewConversionService`.
- Web public methods preserved: `find_soffice_binary`, `get_status`,
  `convert_to_pdf_preview`, `get_cached_pdf_preview`, and
  `schedule_conversion`.
- DocQA public methods preserved: `find_soffice_binary`,
  `convert_to_pdf_preview`, and `get_cached_pdf_preview`. The shared facade adds
  Web status/scheduling methods without removing DocQA behavior.
- Supported Office extensions remain `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`,
  and `.xlsx`.
- Successful facade results remain string paths; converter/source failures
  retain the existing empty-string fallback.
- Cache root remains `$GRADIO_TEMP_DIR/pdf_previews` (or the same system temp
  fallback), and cache filenames retain the exact established
  `<stem>_<legacy-md5[:12]>.pdf` form.
- Existing “Generating PDF preview in background...” and “PDF conversion
  failed. Showing text preview.” notices are unchanged.
- No Gradio input/output tuple, event chain, JSON field, DB model, or session
  shape changed.

## Implementation

### New core

- `ktem.preview.errors`: stable typed error codes and source/converter/stage/path
  context.
- `ktem.preview.models`: source kinds, archive limits, classified source, and
  retry-attempt diagnostics.
- `ktem.preview.source`: PDF/OOXML/CFB signature classification, mismatch and
  corruption rejection, bounded OOXML validation, SHA-256 source identity, and
  legacy cache-signature compatibility.
- `ktem.preview.office`: strict conversion/cache service, focused converter
  runner, same-source locks, bounded semaphore, isolated workspaces and
  `UserInstallation`, retained retry diagnostics, PDF validation, atomic
  `os.replace`, cleanup handling, and the legacy fallback facade.

The cache lookup uses only the exact signature-derived path. The old
`<stem>_*.pdf` directory scan was removed, so equal filenames in different
directories cannot recover one another’s output. A validated existing winner is
never removed by a concurrent loser; invalid entries are replaced only after a
fresh candidate validates.

### Typed errors

All core failures carry `code`, `stage`, `source_path`, `converter`, and
actionable `details`. Coverage includes:

- source missing, corrupt, archive invalid, and declared/detected type mismatch;
- converter unavailable, timeout, and non-zero/failure;
- output missing and invalid;
- cleanup failure;
- retained LibreOffice and docx2pdf retry diagnostics.

The compatibility facade catches only typed `PreviewError` failures, logs all
context fields, and renders the pre-existing empty-string fallback. Broad
converter/PDF boundaries in the core always raise a typed contextual error.

## TDD Evidence

### Initial RED

Command (with temporary `KH_APP_DATA_DIR`):

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py -q
```

Result: `1 failed, 9 passed`. The expected failure showed that the Web and
DocQA import paths still exposed two different conversion classes. The nine
passing tests characterized existing public methods, supported formats, cache
root, return fallback, and notices.

Command:

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_source_core.py \
  libs/ktem/ktem_tests/test_preview_office_core.py -q
```

Result: `29 failed`. Every failure was the expected
`ModuleNotFoundError: No module named 'ktem.preview'` before production code
existed.

### Additional RED cases found during self-review

- Truncated CFB source: `1 failed`; the source was incorrectly accepted instead
  of raising typed `cfb_validation` context.
- Invalid exact cache entry: `1 failed`; `OUTPUT_INVALID` stopped conversion
  before a fresh validated candidate could atomically replace the corrupt
  cache.
- Exact compatibility cache filename: `2 failed`; the new SHA-256 source
  identity had changed the old MD5-derived filename returned by both facades.

Each case was committed as a test before its minimal production correction.

### GREEN

Focused command:

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_source_core.py \
  libs/ktem/ktem_tests/test_preview_office_core.py \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py -q
```

Result: `41 passed`, exit 0.

Relevant ktem package command additionally included import laziness, the
existing indexing conversion utility, runtime defaults, preview ABI/timer,
DocQA runtime/helpers/graph scope, and file-index extraction tests.

Result: `115 passed`, exit 0.

Both pytest runs emitted one existing `CryptographyDeprecationWarning` from
pypdf’s ARC4 provider; there were no test failures.

## Verification Gates

- `python scripts/check_codebase_hygiene.py <all changed Python files>`:
  `No codebase hygiene ratchet violations.`, exit 0.
- `python -m pre_commit run --files <all changed files>`: every hook passed,
  including hygiene, Black, isort, flake8, autoflake, mypy, and codespell.
- `git diff --check`: passed before each commit.
- Baseline: `scripts/codebase_hygiene_baseline.json` is unchanged.
- New/touched budgets after real responsibility split:
  - `preview/office.py`: 536 lines
  - `_OfficeConverterRunner`: 136 lines
  - `OfficeConversionService`: 211 lines
  - `OfficePreviewConversionService`: 115 lines
  - `preview/source.py`: 291 lines
  - no function exceeds 80 lines

The initial implementation placed converter execution and cache orchestration
in one 347-line class. The hygiene gate rejected it. Converter process execution
was then extracted into `_OfficeConverterRunner`; this was a responsibility
split, not mechanical compression.

## Changed Files

- `libs/ktem/ktem/preview/__init__.py`
- `libs/ktem/ktem/preview/errors.py`
- `libs/ktem/ktem/preview/models.py`
- `libs/ktem/ktem/preview/source.py`
- `libs/ktem/ktem/preview/office.py`
- `libs/ktem/ktem/pages/chat/page_preview_office.py`
- `libs/ktem/ktem/docqa/preview_support.py`
- `libs/ktem/ktem_tests/preview_test_utils.py`
- `libs/ktem/ktem_tests/test_preview_source_core.py`
- `libs/ktem/ktem_tests/test_preview_office_core.py`
- `libs/ktem/ktem_tests/test_preview_office_compatibility.py`

## Commit Discipline

- `49323d0` — initial characterization and RED core contract
- `d96a530` — corrupt CFB RED test
- `660fc09` — corrupt-cache recovery RED test
- `7283a39` — exact cache-path compatibility RED test
- `54b616a` — production implementation/refactor

No formatting-only churn or baseline refresh was mixed into the production
commit.

## Self-Review

- Requirements were checked line-by-line against `task-12a-brief.md`.
- Old and new public method sets were compared with AST inspection; no old
  public method is missing.
- The range diff contains no CLI, event wiring, JSON, DB, session,
  indexing/acceptance integration, authorization, DOCX render, or browser code.
- No cache-directory scan remains in the shared service.
- Same-name/different-directory and same-source/cross-instance concurrency are
  explicitly tested.
- Successful output is validated before atomic publication; isolated
  workspace cleanup never targets the final cache file.
- Test fixtures are readable and stay within module/function hygiene budgets.

## Concerns and Follow-Up

1. Scratch is above its inode soft quota and only about 27,500 files below the
   hard limit after required pre-commit hook installation. This needs operator
   cleanup outside this task; no user cache/data deletion was authorized.
2. Converter behavior is exercised with real subprocess boundaries and real PDF
   parsing but a deterministic fake LibreOffice runner. A real LibreOffice
   end-to-end conversion smoke was not run in this slice.
3. The pypdf/cryptography ARC4 deprecation warning is dependency-level and
   pre-existing.
4. Indexing/acceptance integration, authorization, DOCX decomposition, and
   render/browser safety remain explicitly deferred to Task 12B/12C.

## Review Remediation (2026-07-10)

The Task 12A clean review identified four required fixes and three additional
regressions to lock down. Test commits `73f8f53` and `f30fa98` captured those
cases before production commit `4411a70` implemented the corrections.

### Corrections

- Workspace cleanup now runs from a true `finally` boundary. Unexpected
  converter, staging-directory, and atomic-publication exceptions are logged
  with file/stage/converter context, wrapped as typed conversion failures, and
  cannot bypass cleanup.
- A cleanup-only failure after a validated PDF has been published is an
  actionable warning and no longer changes a successful result into facade
  failure. When conversion and cleanup both fail, the typed cleanup error
  retains the primary failure details and conversion attempts.
- Conversion capacity is now shared process-wide across service instances.
  Same-cache/source lock entries count active and waiting users and are removed
  when the final user exits, so the keyed-lock registry does not grow without
  bound.
- CFB classification now reads the actual directory stream names through the
  header, DIFAT, FAT, and directory chains. `WordDocument`, `Workbook`/`Book`,
  and `PowerPoint Document` determine `.doc`, `.xls`, and `.ppt`; unknown,
  conflicting, corrupt, and declared/detected mismatch containers are rejected
  with typed `cfb_validation` or source-mismatch context.
- Legacy cache identity preserves the unresolved absolute input path. A real
  target and a symlink alias retain their distinct established MD5-derived
  filenames and cannot reuse one another's in-memory cache entry.
- OOXML compression-ratio enforcement and concurrent failed-loser safety now
  have explicit regressions.

The limiter and keyed locks are intentionally process-local; they prevent
duplicate work and enforce capacity within one Python process. Cross-process
correctness does not depend on a fragile filesystem mutex: every contender has
its own workspace and LibreOffice profile, validates its candidate, publishes
with atomic `os.replace`, and cleans only its own workspace. Two processes may
therefore both perform conversion, but a failed loser cannot remove a valid
winner. The concurrent-loser regression bypasses the process lock explicitly
to exercise this safety boundary.

### Review TDD Evidence

The first review RED run covered actual CFB subtype/mismatch/unknown streams,
the shared limiter, lock reclamation, unexpected exception cleanup,
cleanup-only success, failure-plus-cleanup context, concurrent-loser safety,
symlink cache naming, compression-ratio limits, and scheduled-facade status.

Result: `13 failed, 43 passed`. The failures matched the review gaps; the
compression-ratio and failure-plus-cleanup tests passed immediately as useful
characterization.

A self-review then strengthened the symlink regression to convert both a real
target and its alias through the same service. Result before the production
cache-map correction: `1 failed` because the alias reused the target's cached
path.

Focused GREEN command:

```bash
uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_source_core.py \
  libs/ktem/ktem_tests/test_preview_office_core.py \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py -q
```

Result: `56 passed`, exit 0.

The relevant ktem regression command additionally covered import laziness, the
existing indexing conversion utility, runtime defaults, preview ABI/timer,
DocQA runtime/helpers/graph scope, and file-index extraction.

Result: `130 passed`, exit 0. Both GREEN runs emitted only the existing pypdf
ARC4 `CryptographyDeprecationWarning`.

The standard CFB test fixture was also opened with `olefile.OleFileIO`; the
reported stream lists were `WordDocument`, `PowerPoint Document`, and
`Workbook` for `.doc`, `.ppt`, and `.xls`, respectively.

### Review Verification and Diagnostics

- Explicit hygiene over all review-changed Python files:
  `No codebase hygiene ratchet violations.`, exit 0.
- Changed-file pre-commit: every hook passed, including hygiene, Black, isort,
  flake8, autoflake, mypy, and codespell.
- `git diff --check`: passed before the implementation commit.
- `scripts/codebase_hygiene_baseline.json`: unchanged.
- Current budgets: `preview/coordination.py` 84 lines,
  `preview/office.py` 596 lines, and `preview/source.py` 442 lines;
  `_OfficeConverterRunner` is 136 lines, `OfficeConversionService` 277 lines,
  `OfficePreviewConversionService` 115 lines, and no function reaches 70 lines.
- Black changed only newly edited functional regions; there was no unrelated
  formatting-only churn.

The first post-fix hygiene command exited 1 because the unexpected-exception
catch stored a typed failure but did not itself emit an actionable diagnostic.
Adding the contextual error log satisfied the broad-catch contract; the next
hygiene and pre-commit runs passed. A one-off AST budget inspection also exited
1 because it tried to read `lineno` from the module node; restricting the
inspection to function and class nodes corrected the diagnostic, which then
reported the budgets above.

### Review Changed Files

- `libs/ktem/ktem/preview/coordination.py`
- `libs/ktem/ktem/preview/models.py`
- `libs/ktem/ktem/preview/office.py`
- `libs/ktem/ktem/preview/source.py`
- `libs/ktem/ktem_tests/preview_test_utils.py`
- `libs/ktem/ktem_tests/test_preview_source_core.py`
- `libs/ktem/ktem_tests/test_preview_office_core.py`
- `libs/ktem/ktem_tests/test_preview_office_compatibility.py`

The public `MARA`/`MARA-cli`, Web, DocQA, Gradio, DB, JSON, and session surfaces
remain unchanged. Final storage checks still show `.venv` linked to fastscratch,
runtime data on fastscratch, and no repository-root `data/`, `datasets/`, or
`outputs/`. Fastscratch is at 295.8G and 471,857 files; scratch is at 71.91G and
472,450 files, still above its inode soft quota with grace active. No user data
or caches were deleted.
