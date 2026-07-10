# Task 12B Report: DOCX Preview Decomposition and Safe Rendering

## Outcome

Task 12B is implemented on top of base
`7217a94feee733a6cbef7a55e8b0cb12bff94113` in the isolated worktree
`/mnt/scratch/users/tbczhang/projects/MARA-quality-hardening`.

DOCX text extraction, rich HTML rendering, relationship/image handling, table
rendering, and pagination now live in focused no-Gradio modules under
`ktem.preview`. The Web and DocQA entrypoints retain their established function
names and fallback values while re-exporting one shared implementation.

This slice does not change shared context, authorization, browser wiring,
Gradio components, tuple shapes, event-chain order, CLI commands, DB models,
JSON/session shapes, Office/PDF cache paths, or conversion notices.

## Storage and Runtime Preflight

- Worktree HEAD began exactly at the requested base.
- `.venv` is a symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Python resolves to
  `/mnt/fastscratch/users/tbczhang/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10`.
- uv, Python, Hugging Face, Codex, and MARA runtime variables point to
  fastscratch. `PRE_COMMIT_HOME=/users/tbczhang/scratch/pre-commit-cache` reused
  the existing hook cache; no dependency install or model/data download was
  requested.
- Every pytest command used a fresh temporary `KH_APP_DATA_DIR` under
  `$MARA_RUNTIME_DIR`, removed by a shell trap after the run. The new tests also
  replace `KH_APP_DATA_DIR` with their `tmp_path` fixture.
- Repository-root `data/`, `datasets/`, and `outputs/` are absent.
- Final fastscratch quota: 295.8G used, 471,866/500,000 soft-limit files.
- Final scratch quota: 71.91G used, 472,573/300,000 soft-limit files and
  500,000 hard-limit files, with grace active.
- No `task12b-*` runtime directories remained after verification.

Scratch was already above its inode soft limit at preflight. This task reused
the installed environment and pre-commit cache and did not delete user data or
caches.

## Public Surface and Compatibility

- Preserved Web imports from
  `ktem.pages.chat.page_preview_document`:
  `extract_docx_text`, `extract_docx_html`, and `paginate_docx_html`.
- Preserved the DocQA import from `ktem.docqa.preview_support`:
  `extract_docx_text`.
- The Web and DocQA text functions now re-export the same shared function
  object. Their successful text and `max_chars` output is equivalent.
- Missing, corrupt, and malformed compatibility inputs still return `""`.
  They now emit a contextual warning with code, path, stage, converter, and
  details instead of silently swallowing the failure.
- Existing rich headings, spans, bold/italic/underline, color, safe links,
  nested-list markup, paragraph clipping, page-break pagination, page clamp,
  and non-PDF page-cache behavior are locked by characterization tests.
- The successful DOCX wrapper and established pagination wrapper remain
  unchanged for characterized content.
- `MARA` and `MARA-cli` have no command, option, import, or dispatch changes.
- No Gradio/event files were edited, so component counts and event order are
  outside the write set and unchanged.

## Implementation Boundaries

- `ktem.preview.docx`: strict and compatibility entrypoints plus actionable
  fallback logging.
- `ktem.preview.docx_package`: source validation, typed package/XML failures,
  python-docx loading, and shared text extraction.
- `ktem.preview.docx_relationships`: hyperlink and embedded-image relationship
  resolution.
- `ktem.preview.docx_security`: URL scheme policy, safe font names, raster MIME
  allowlist, signature matching, and the decoded-payload size bound.
- `ktem.preview.docx_runs`: XML text/break/tab/image rendering and rich run
  formatting.
- `ktem.preview.docx_blocks`: numbering, paragraph/list markup, table cells,
  and table rendering.
- `ktem.preview.docx_render`: document-order paragraph/table traversal,
  max-character accounting, list-stack output, and root HTML rendering.
- `ktem.preview.docx_pagination`: block discovery, height estimation, explicit
  page breaks, table preservation, and page wrappers.
- `page_preview_document.py`: a five-line compatibility re-export facade.
- `docqa.preview_support`: imports shared DOCX text extraction; the duplicate
  implementation and its silent broad catch were removed.

## Rendering Security

- Hyperlinks render as anchors only for `http`, `https`, and `mailto`.
- `javascript`, `data`, `file`, relative traversal, absent-host HTTP(S),
  whitespace/control-character targets, and malformed URLs render only their
  already-escaped visible text.
- Link targets are escaped before entering `href` and keep
  `target="_blank" rel="noopener noreferrer"` for allowed links.
- XML text and image alt text are escaped before HTML output.
- Run and base font names use a conservative character policy before entering
  inline CSS.
- Embedded images use an explicit `image/png`, `image/jpeg`, `image/gif`, and
  `image/webp` allowlist, a 5 MiB decoded-payload limit, and MIME-specific magic
  checks before a data URL is created.
- SVG, HTML, non-raster, MIME/signature mismatches, and oversized image payloads
  never enter a data URL. Their escaped alt text remains visible when present.
- Corrupt and truncated strict boundaries raise `PreviewSourceError` with a
  stable error code, resolved source path, stage, and `python-docx` converter
  context.

## TDD Evidence

### Existing baseline

Before adding Task 12B tests:

```bash
KH_APP_DATA_DIR=<fastscratch-temp> uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_source_core.py \
  libs/ktem/ktem_tests/test_preview_coordination.py \
  libs/ktem/ktem_tests/test_preview_office_core.py \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py \
  libs/ktem/ktem_tests/test_chat_gradio_preview_adapter.py \
  libs/ktem/ktem_tests/test_chat_preview_timer.py -q
```

Result: `65 passed`, exit 0.

### Initial RED

The first collection attempt exited 2 because a newly written assertion had an
unterminated string literal. That was a test defect rather than valid RED; the
quote was corrected before accepting any failure as evidence.

Valid RED command:

```bash
KH_APP_DATA_DIR=<fastscratch-temp> uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_docx_core.py \
  libs/ktem/ktem_tests/test_preview_docx_compatibility.py -q --tb=short
```

Result before production changes: `15 failed, 11 passed`, exit 1.

The expected failures showed that:

- five unsafe hyperlink forms still produced anchors;
- table and image content was not rendered;
- tables disappeared during pagination;
- `ktem.preview.docx` strict/shared APIs did not exist;
- corrupt compatibility fallback emitted no actionable diagnostics; and
- Web/DocQA functions were not shared re-exports.

The eleven passing tests characterized the existing rich HTML, allowed links,
XML escaping, nested lists, max-character clipping, page-break pagination,
missing/corrupt empty fallback, text equivalence, page clamp, and page cache.

Tests and readable fixture helpers were committed before implementation in
`f974462`.

### Security GREEN

After the URL and embedded-content policy commit:

```bash
KH_APP_DATA_DIR=<fastscratch-temp> uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_docx_core.py -q -k hyperlink
```

Result: `9 passed, 13 deselected`, exit 0.

### Functional GREEN

After the shared core and compatibility facades were connected, the original
focused command returned `26 passed`, exit 0.

During self-review, the new paragraph renderer was found to emit a positive
first-line indent on a list item, while the old renderer intentionally omitted
that style. A new characterization test was added and run before the fix:

```bash
KH_APP_DATA_DIR=<fastscratch-temp> uv run --python 3.10 python -m pytest \
  libs/ktem/ktem_tests/test_preview_docx_core.py::test_list_first_line_indent_remains_ignored -q
```

RED result: `1 failed`, showing
`<li style="text-indent:24pt;">`; test commit `b29c09b`.

GREEN result after the minimal block-renderer correction: `1 passed`.

Final focused result: `27 passed`, exit 0.

No security assertion was weakened to obtain GREEN.

## Verification Gates

### Relevant ktem regression gate

The final relevant command covered new DOCX tests, source/coordination/Office
preview, Web compatibility/timer ABI, import laziness, runtime defaults,
existing Office conversion, DocQA runtime/helpers/graph scope, and file-index
page extraction.

Result: `162 passed`, exit 0, in 9.19 seconds.

All focused and relevant pytest runs emitted only the existing pypdf
`CryptographyDeprecationWarning` for ARC4.

### Hygiene and baseline

```bash
uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>
```

Result: `No codebase hygiene ratchet violations.`, exit 0.

```bash
uv run --python 3.10 python scripts/check_hygiene_baseline.py \
  --base-ref 7217a94feee733a6cbef7a55e8b0cb12bff94113
```

Result: baseline did not widen, exit 0.

The baseline was manually downshifted only for measured debt that disappeared:

- removed `page_preview_document.py`'s 394-line module, 277-line HTML function,
  89-line pagination function, and 11 broad-catch exemption;
- reduced `docqa.preview_support.py` from 561 to 364 measured lines, removed the
  stale moved Office method exemption, and reduced non-actionable broad catches
  from 18 to 11.

No baseline update/generation command was run against the tracked baseline. A
temporary baseline path under `$MARA_RUNTIME_DIR` was used only to measure the
two touched compatibility files before applying the exact downshift by patch.

### Changed-file pre-commit

```bash
uv run --python 3.10 python -m pre_commit run --files <changed-files>
```

Result: every hook passed, including hygiene, Black, isort, flake8, autoflake,
mypy, and codespell.

The first pre-commit attempt mistakenly used `/usr/bin/python -m pre_commit`
and exited 1 because that interpreter does not contain `pre_commit`. Re-running
through the mandated uv Python resolved the command issue. Initial hook passes
also added missing EOFs and ordered newly introduced imports; the next runs
were clean. There was no unrelated formatting-only churn.

`git diff --check` passed before each commit and the worktree was clean before
writing this report.

## Budgets

Final production module sizes:

- `docx.py`: 64 lines
- `docx_blocks.py`: 187 lines
- `docx_package.py`: 107 lines
- `docx_pagination.py`: 76 lines
- `docx_relationships.py`: 63 lines
- `docx_render.py`: 118 lines
- `docx_runs.py`: 124 lines
- `docx_security.py`: 84 lines
- `page_preview_document.py`: 5 lines
- `docqa.preview_support.py`: 364 lines

The hygiene gate confirms every new/touched DOCX function is below 80 lines,
every class is below 300 lines, every new module is below 600 lines, and the
new DOCX core plus Web facade contain zero non-actionable broad catches.

## Changed Files

Production and baseline:

- `libs/ktem/ktem/preview/docx.py`
- `libs/ktem/ktem/preview/docx_blocks.py`
- `libs/ktem/ktem/preview/docx_package.py`
- `libs/ktem/ktem/preview/docx_pagination.py`
- `libs/ktem/ktem/preview/docx_relationships.py`
- `libs/ktem/ktem/preview/docx_render.py`
- `libs/ktem/ktem/preview/docx_runs.py`
- `libs/ktem/ktem/preview/docx_security.py`
- `libs/ktem/ktem/pages/chat/page_preview_document.py`
- `libs/ktem/ktem/docqa/preview_support.py`
- `scripts/codebase_hygiene_baseline.json`

Tests:

- `libs/ktem/ktem_tests/docx_preview_test_utils.py`
- `libs/ktem/ktem_tests/test_preview_docx_core.py`
- `libs/ktem/ktem_tests/test_preview_docx_compatibility.py`

Report:

- `.superpowers/sdd/task-12b-report.md`

## Commit Discipline

- `f974462` — characterization and security RED tests
- `ec90434` — hyperlink and embedded-content security policy
- `b29c09b` — self-review list-indentation characterization RED
- `5841062` — shared DOCX core, table/image rendering, strict errors,
  compatibility re-exports, duplicate removal, and measured baseline downshift

No pure formatting changes were needed beyond formatting the newly edited
semantic regions, so no empty formatting-only commit was created.

## Self-Review

- Re-read `task-12b-brief.md`, the parent Task 12 brief/detail, and both
  development contracts against the final diff.
- Confirmed the diff contains no shared context, authorization, event
  registration, browser/Playwright, CLI, DB model, JSON, or session edits.
- Confirmed public function identity and successful/fallback outputs through
  compatibility tests.
- Confirmed rendered text, href values, alt text, and table cell text cannot
  inject raw HTML in the covered paths.
- Confirmed disallowed URL and image inputs retain escaped visible text rather
  than becoming active content.
- Confirmed table blocks remain in document order and survive pagination.
- Confirmed non-PDF page caching and page clamping still compute once and reuse
  the same cache entries.
- Confirmed all compatibility fallbacks catch typed preview failures rather
  than broad, silent exceptions.
- Confirmed tracked hygiene debt only moved downward.

## Concerns and Follow-Up

1. Scratch remains above its inode soft quota and is only about 27,400 files
   below the hard limit. Operator-led cache cleanup remains necessary outside
   this task; no deletion authority was inferred.
2. `docqa.preview_support.py` retains 11 pre-existing non-actionable broad
   catches in non-DOCX text/XLSX/PPTX/resolution paths. Task 12B removed the
   duplicated DOCX catch and all DOCX-core/page catches, but did not expand into
   unrelated format behavior. The baseline records the measured reduction.
3. DOCX pagination remains a deterministic height heuristic, not a Word layout
   engine. This task preserves its established behavior while adding table
   blocks and explicit page-break coverage.
4. The raster allowlist intentionally excludes SVG, TIFF, BMP, and other
   formats. Unsupported or invalid embedded images display escaped alt text
   instead of active data content.
5. The pypdf/cryptography ARC4 warning is dependency-level and pre-existing.
