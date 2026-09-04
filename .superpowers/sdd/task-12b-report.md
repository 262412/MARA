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

## Review Remediation (2026-07-11)

The review-hardened Task 12B implementation head is `a7367d6`, on top of the
reported Task 12B head `15efd92`. Review protection tests were committed first
in `bb4283f`; archive/render security is isolated in `4df1d64`, and strict
typed-boundary compatibility fixes are isolated in `a7367d6`.

### Reviewed Corrections

- Both strict paths now run the shared OOXML classifier before either
  `python-docx` package loading or direct `word/document.xml` extraction. Its
  10,000-entry, 512 MiB aggregate-uncompressed, and 1,000x per-entry ratio
  policy applies to the entire package, including relationship entries, before
  python-docx can traverse or decompress them. The bounded `testzip()` integrity
  pass runs only after those metadata limits.
- Resource-limit failures retain `SOURCE_ARCHIVE_INVALID`,
  `stage=archive_validation`, resolved source path, and converter
  `python-docx`. Other corrupt-package failures retain the established
  `docx_package` stage and DOCX-specific diagnostic wording.
- Every HTML renderer owns one image budget: at most 16 safe raster
  occurrences and 5 MiB aggregate decoded bytes. MIME, signature, and 5 MiB
  per-image checks run before the aggregate budget; budget consumption happens
  before base64 encoding. Rejected occurrences keep escaped alt text.
- Rendered HTML has an 8 MiB final character budget. Paragraph/table admission
  is block-atomic, including list-stack rollback, so the renderer stops before
  an over-budget block and still returns a complete wrapper rather than a
  truncated tag. Image-only paragraphs can no longer bypass bounds when
  `max_chars=1` contributes no text characters.
- Invalid `None` and embedded-NUL source inputs now become typed
  `SOURCE_INVALID` errors at `stage=docx_source`. The diagnostic uses a safe
  placeholder path and retains `repr()` of the rejected input in details.
- Both python-docx exception families are translated at strict load/render
  boundaries: `PythonDocxError` and `XmlchemyError`, including
  `docx.oxml.exceptions.InvalidXmlError` from missing required XML attributes.
  Compatibility entrypoints therefore keep returning `""` while logging code,
  stage, source, converter, and details.

The Web/DocQA function objects and signatures, successful/fallback return
shapes, HTML wrapper, page cache, pagination, Gradio/event wiring, CLI, DB,
JSON/session, and preview-cache surfaces are unchanged.

### Review TDD Evidence

The final pre-production RED command selected only the reviewed regressions
from the DOCX core and compatibility files. Result: `17 failed, 27 deselected`,
exit 1. The failures showed:

- four strict text/HTML cases accepted high-ratio package or relationship
  entries;
- image-only rendering emitted 20 data URLs despite the 16-occurrence contract,
  emitted three 2 MiB images despite the 5 MiB aggregate contract, and exceeded
  the 8 MiB final HTML contract at `max_chars=1`;
- strict text/HTML leaked native `TypeError` or NUL `ValueError`, and all four
  compatibility calls leaked the same exceptions; and
- strict and compatibility HTML leaked
  `docx.oxml.exceptions.InvalidXmlError` for `<w:gridSpan/>` without required
  `w:val`.

Security GREEN selected archive and render-budget cases: `7 passed, 28 deselected`, exit 0. The security-only compatibility regression then passed
`34` cases with the typed-boundary cases intentionally deselected.

Typed-boundary GREEN: `10 passed, 34 deselected`, exit 0.

Final focused DOCX result: `44 passed`, exit 0. The relevant ktem gate added
source/coordination/Office preview, Web ABI/timer, import laziness, runtime
defaults, existing conversion, DocQA runtime/helpers/graph scope, and
file-index extraction: `179 passed`, exit 0 in 10.59 seconds. Pytest emitted
only the existing pypdf ARC4 `CryptographyDeprecationWarning`.

### Review Verification and Diagnostics

- Explicit hygiene over all eight review-changed Python files:
  `No codebase hygiene ratchet violations.`, exit 0.
- Baseline guard against `15efd92`:
  `Hygiene baseline did not widen`, exit 0. The tracked baseline is unchanged.
- Changed-file pre-commit passed hygiene, Black, isort, flake8, autoflake,
  mypy, and codespell.
- `git diff --check` passed for working-tree and review commit-range checks.
- Current production sizes are: `docx.py` 75 lines, `docx_package.py` 144,
  `docx_relationships.py` 72, `docx_render.py` 164, and `docx_security.py` 110.
  The hygiene gate confirms no function reaches 80 lines.

The first archive fixture rewrite exited 1 in four cases because modifying an
existing XML member did not reliably exceed the central 1,000x threshold; it
was replaced with genuine small high-ratio package and `.rels` entries that
python-docx currently ignores. The first aggregate-image GREEN run exited 1
because its zero-filled payload was itself a compression-ratio bomb, so the
new archive guard correctly rejected it before render. The aggregate and
existing oversized-image fixtures now use deterministic low-compression bytes,
preserving their intended render-boundary assertions. Rewrapped corrupt-package
details also regained the established `DOCX` wording.

The first test pre-commit and first production pre-commit runs exited 1 only
because Black formatted new long regions and isort reordered new imports.
Immediate reruns were clean; no unrelated formatting-only churn was committed.
The first report pre-commit likewise exited 1 only to apply Prettier's Markdown
reflow; its immediate rerun passed.

### Review Changed Files

- `libs/ktem/ktem/preview/docx.py`
- `libs/ktem/ktem/preview/docx_package.py`
- `libs/ktem/ktem/preview/docx_relationships.py`
- `libs/ktem/ktem/preview/docx_render.py`
- `libs/ktem/ktem/preview/docx_security.py`
- `libs/ktem/ktem_tests/docx_preview_test_utils.py`
- `libs/ktem/ktem_tests/test_preview_docx_core.py`
- `libs/ktem/ktem_tests/test_preview_docx_compatibility.py`

Residual risk remains intentionally bounded: the validator still decompresses
members during `testzip()`, but only after entry, aggregate-size, and ratio
limits have accepted their central-directory metadata; the final HTML limit
omits a whole over-budget block rather than partially rendering it. DOCX
pagination remains the previously documented heuristic.

Final review storage checks show `.venv`, Python, caches, and runtime data on
approved fastscratch paths and no repository-root `data/`, `datasets/`, or
`outputs/`. Fastscratch is at 295.8G and 471,883/500,000 soft files. Scratch is
at 71.91G and 472,609/300,000 soft files, still in inode grace. No user data or
caches were deleted.

## Review Remediation Round 2 (2026-07-11)

The second review round is implemented in three behavior-separated commits:
`9ce5053` adds failing protections, `0724613` preallocates DOCX render
resources, and `52e777f` binds archive validation and parsing to one opened
file handle while adding a structured error reason.

### Round 2 Corrections

- One exact remaining-character budget is shared by the relationship, run,
  paragraph, table, and document block renderers. It reserves the root/list,
  block, run, hyperlink, image, and fallback-alt wrappers as they are admitted.
  A rejected block restores both its HTML and image-budget checkpoints, so no
  partial block or unclosed tag enters the result and final output remains at
  or below 8 MiB.
- XML text, hyperlink targets, and image alt text have their escaped expansion
  counted before `html.escape` is called. The counter handles the exact Python
  HTML entities for ampersands, angle brackets, and quoted characters without
  first allocating the escaped string. An over-budget required value rejects
  its block; an over-budget optional hyperlink target keeps its already-safe
  visible label without an anchor.
- Safe raster images reserve their exact base64 encoded length, data-URL
  prefix, image wrapper, and escaped alt expansion before aggregate image
  accounting and `base64.b64encode`. If the complete image cannot fit, no
  encoded payload is allocated and the renderer tries the bounded escaped-alt
  fallback instead.
- Strict text and HTML extraction now open the source once and pass that same
  binary handle through ZIP metadata limits, `testzip()` integrity validation,
  and the subsequent python-docx or `word/document.xml` read. Replacing the
  source path after validation therefore cannot redirect parsing to a different
  unvalidated archive.
- `PreviewError` has an additive, default-empty `reason` field. OOXML resource
  limits use `archive_resource_limit`; corrupt and structurally invalid
  archives use their own reasons. DOCX stage routing now checks the structured
  reason instead of searching diagnostic prose for `"exceeds"`.

These changes preserve the strict and compatibility function names and
signatures, established HTML for admitted content, Web/DocQA re-exports,
fallback values, pagination, cache behavior, Gradio/event wiring, CLI, DB, and
JSON/session surfaces.

### Round 2 TDD Evidence

The focused RED command selected the two new test modules before production
changes. Result: `7 failed`, exit 1. The failures proved that:

- an image could reach `base64.b64encode` after preceding HTML had exhausted
  the remaining budget;
- oversized run text, hyperlink targets, and image alt text reached
  `html.escape` before final admission;
- replacing the source path from inside `ZipFile.testzip()` made strict text
  and HTML parse the unvalidated replacement; and
- archive resource errors had no structured `reason`.

After the render-budget commit, DOCX core, compatibility, and budget coverage
returned `48 passed`, exit 0. A mixed DOCX/source gate after the snapshot fix
returned `77 passed`, exit 0. The full relevant gate reused the previous 179
tests and added the seven new regressions:

```bash
KH_APP_DATA_DIR=<fastscratch-temp> uv run --python 3.10 python -m pytest -q \
  libs/ktem/ktem_tests/test_preview_docx_core.py \
  libs/ktem/ktem_tests/test_preview_docx_compatibility.py \
  libs/ktem/ktem_tests/test_preview_docx_budget.py \
  libs/ktem/ktem_tests/test_preview_docx_snapshot.py \
  libs/ktem/ktem_tests/test_preview_source_core.py \
  libs/ktem/ktem_tests/test_preview_coordination.py \
  libs/ktem/ktem_tests/test_preview_office_core.py \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py \
  libs/ktem/ktem_tests/test_chat_gradio_preview_adapter.py \
  libs/ktem/ktem_tests/test_chat_preview_timer.py \
  libs/ktem/ktem_tests/test_import_laziness.py \
  libs/ktem/ktem_tests/test_runtime_defaults.py \
  libs/ktem/ktem_tests/test_office_conversion.py \
  libs/ktem/ktem_tests/test_docqa_runtime.py \
  libs/ktem/ktem_tests/test_docqa_runtime_helpers.py \
  libs/ktem/ktem_tests/test_docqa_runtime_graph_scope.py \
  libs/ktem/ktem_tests/test_file_index_page_extraction.py --tb=short
```

Result: `186 passed`, exit 0 in 11.18 seconds. The only warning was the
pre-existing pypdf ARC4 `CryptographyDeprecationWarning`.

The first source-classifier regression run returned `2 failed, 75 passed`
because the initial single-handle refactor checked a declared OOXML extension
before an actual PDF/CFB signature. Restoring real-signature priority fixed the
regression without weakening the snapshot behavior; the immediate rerun
returned `77 passed`. One earlier focused command exited 4 because it named a
nonexistent `test_preview_docx_invalid_inputs.py`; using the repository's four
actual `test_preview_docx*.py` modules corrected the test selection. The first
security pre-commit run exited 1 only because Black reformatted the edited block
and render modules; the clean rerun passed.

### Round 2 Verification and Storage

- Explicit hygiene over all ten R2 Python files reported
  `No codebase hygiene ratchet violations.`, exit 0.
- `scripts/check_hygiene_baseline.py --base-ref def6b67` reported that the
  hygiene baseline did not widen. The tracked baseline was not edited.
- Changed-file pre-commit passed hygiene, Black, isort, flake8, autoflake,
  mypy, and codespell. Commit-range and working-tree `git diff --check` passed.
- The HTML budget ledger was checked on a document containing heading, escaped
  text, hyperlink, nested list, table, and raster image; its reserved count
  exactly matched the final HTML length (`581 == 581`).
- Final production sizes are `docx_blocks.py` 208 lines, `docx_package.py` 164,
  `docx_relationships.py` 87, `docx_render.py` 200, `docx_runs.py` 157,
  `docx_security.py` 170, `errors.py` 70, and `source.py` 468. The hygiene gate
  confirms that no new function or class exceeds its contract budget.
- `.venv`, Python, caches, and runtime paths remain on their contracted
  fastscratch locations; repository-root `data/`, `datasets/`, and `outputs/`
  remain absent. Fastscratch is at 295.8G and 471,891/500,000 soft files.
  Scratch is at 71.91G and 472,652/300,000 soft files, still in inode grace.
  All `task12b-r2-*` runtime directories created by verification were empty and
  removed with `rmdir`; no user data or cache was deleted.

Round 2 changed the eight production modules listed above and added
`test_preview_docx_budget.py` plus `test_preview_docx_snapshot.py`; this report
is the only documentation change. Residual risk remains bounded by the existing
512 MiB aggregate archive policy: validation still decompresses accepted
members during `testzip()`, and the approved single-handle design prevents path
replacement but is not a copied byte snapshot against a writer modifying the
already-open inode in place. DOCX pagination remains the existing heuristic.

## Review Remediation Round 3 (2026-07-11)

Round 3 is isolated in `a8040f8` (tests first) and `13ba62b` (minimal
production fix).

### Round 3 Corrections

- `escaped_html_length()` now counts a single quote exactly as Python
  `html.escape(..., quote=True)` emits it: `&#x27;` is six characters, so the
  expansion delta is five rather than four. Large single-quote run text,
  hyperlink targets, and image alt text are therefore rejected before
  `html.escape` when their real expansion cannot fit. The shared ledger and
  final output remain within the 8 MiB character budget.
- A DOCX member whose ZIP compression method is unknown now receives the
  specific structured reason `archive_unsupported_compression` at archive
  inspection. Strict HTML retains `SOURCE_ARCHIVE_INVALID`, the established
  `docx_package` boundary stage, resolved source path, and `python-docx`
  converter context. Compatibility HTML returns `""` and its warning now
  includes the structured reason alongside code, stage, path, converter, and
  details.

The review's reported bare `NotImplementedError` was not reproducible at the
Round 2 head: Python's `NotImplementedError` subclasses `RuntimeError`, so the
existing archive branch already converted it to `PreviewSourceError` with the
generic `archive_corrupt` reason, and compatibility HTML already returned an
empty string. Round 3 narrows that existing behavior to the actionable reason
and makes the reason visible in compatibility diagnostics; it does not broaden
the exception boundary.

### Round 3 TDD and Verification

A real DOCX fixture has both its local-file header and central-directory entry
patched to compression method 99. Together with the large single-quote cases,
the pre-production command returned `6 failed, 7 passed`, exit 1:

- text, hyperlink, and image alt values reached the guarded `html.escape`;
- the exact estimator reported 20,480 characters where `html.escape` produced
  24,576;
- strict HTML reported the generic `archive_corrupt` reason; and
- compatibility logging omitted the unsupported-compression reason.

After the two-line estimator/reason behavior and the compatibility diagnostic
change, the targeted command returned `13 passed`, exit 0. Final focused DOCX
coverage returned `57 passed`, exit 0 in 10.19 seconds. The established relevant
gate returned `192 passed`, exit 0 in 11.73 seconds. Both larger gates emitted
only the pre-existing pypdf ARC4 `CryptographyDeprecationWarning`.

- Explicit hygiene over all six R3 Python files reported no ratchet violations.
- `scripts/check_hygiene_baseline.py --base-ref a5feffb` reported that the
  baseline did not widen; the tracked baseline remains unchanged.
- Changed-file pre-commit passed hygiene, Black, isort, flake8, autoflake,
  mypy, Prettier, and codespell. Commit-range and working-tree diff checks
  passed.
- Current touched production sizes are `docx.py` 77 lines,
  `docx_security.py` 170, and `source.py` 476. No function or class exceeds its
  hygiene contract budget.

The first exploratory method-99 probe mistakenly used the system Python and
exited 1 with `ModuleNotFoundError: docx`; the identical probe through
`uv run --python 3.10` reproduced the real archive call stack. The first
attempt to read the testing anti-pattern reference used the skill directory
instead of its nested `test-driven-development` directory and exited 2; an
`rg --files` lookup located and loaded the required reference before tests were
written.

R3 changes only `docx.py`, `docx_security.py`, `source.py`, the DOCX fixture
helper, the two focused regression modules, and this report. Public extraction
function names/signatures, Web/DocQA re-exports, successful HTML, fallback
shapes, pagination/cache behavior, Gradio/event wiring, CLI, DB, and persisted
JSON/session surfaces remain unchanged.

Final storage checks show fastscratch at 295.8G and 471,884/500,000 soft files.
Scratch is at 71.91G and 472,675/300,000 soft files, still in inode grace. No
`task12b-r3-*` runtime directories remain, and no user data or caches were
deleted. Residual archive and pagination risks remain as recorded in Round 2.
