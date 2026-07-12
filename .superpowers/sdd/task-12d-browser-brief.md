# Task 12D: Browser Preview Safety, Real Flows, and Ratchet

Task 12D is the browser-facing closeout for `task-12-detail.md` sections 12.3
and 12.4. Start only after Task 12C2 has stabilized owner-aware source
resolution and the shared preview service. Work tests-first and keep security
tests, production changes, baseline downshifts, and formatting in separate
commits.

## 1. Do not repeat completed work

Task 4 already completed and must remain as characterization, not be rewritten:

- `safe_dom.js` uses text nodes, DOM Range, explicit `<mark>` creation, and
  owned-highlight cleanup instead of untrusted `innerHTML`/`outerHTML` writes.
- answer/evidence HTML passes through the `nh3` allowlist; `javascript:` and
  `data:text/html` answer links are already rejected.
- the main preview iframe and modal PDF iframe already receive sandbox and
  `referrerpolicy` attributes.
- the existing Node suite checks DOM sinks and basic sandbox tokens.
- the existing two Playwright cases prove hostile text and rendered answers are
  inert in real Chromium.

Task 8A1 already completed and must not be repackaged or re-extracted by this
task:

- the only supported viewer is Mozilla PDF.js `6.1.200`;
- the vendored archive SHA-256 remains
  `9e1584d768ed099aa4be27ea423f89a038c2005f1ee417ea4f35ba4591ec1846`;
- runtime materialization remains
  `KH_APP_DATA_DIR/assets/pdfjs/6.1.200`;
- all 406 regular runtime files, the exact file set, symlink rejection, and
  startup revalidation remain owned by `ktem.assets.pdfjs_assets`;
- preview selection, page navigation, and polling must never download,
  re-extract, repair, or rewrite PDF.js.

The missing coverage is the real preview lifecycle. Current Playwright tests
serve a static DOM page and a renderer-only page; they do not launch Gradio,
upload binary PDF/DOCX/PPTX files, select a source, navigate PDF.js, poll an
Office conversion, inspect file-serving allowlists, or exercise corrupt Office
diagnostics.

## 2. Concrete current gaps

1. `launcher.py` and `sso.py` allow all of `ASSETS_DIR`, `KH_DOC_DIR`,
   `GRADIO_TEMP_DIR`, and `KH_FILESTORAGE_PATH`. This exposes far more than the
   verified PDF.js tree and the dedicated visible preview cache.
2. `page_preview_runtime.ensure_pdf_preview_copy` uses a basename-only target
   under `pdf_previews`; different source directories can collide and original
   source PDFs are still used directly in viewer URLs.
3. `page_preview_runtime.notice_html` interpolates its message without HTML
   escaping.
4. `page_preview_presentation.py` emits a run hyperlink without a scheme
   allowlist and trusts `shape.image.content_type` for a `data:` URL. It still
   has 17 broad catches and a 483-line class.
5. `main.js` accepts arbitrary inline HTML, arbitrary `data:text/html`, generic
   `data:image*`, and `.svg` as preview sources. The `ktem-scripted=1` marker is
   browser-forgeable and therefore cannot establish trusted script provenance.
6. `ChatPagePreviewController` is 791 lines and its polling branch silently
   catches `Exception`. `preview_refresh_timer` is inactive, so the documented
   placeholder -> converted PDF polling flow cannot occur in a live page.
7. `page_preview_runtime`, `page_preview_resolver`, `page_preview_spreadsheet`,
   `page_preview_text`, and `page_preview_types` retain silent broad catches.
   The hygiene baseline also still contains completed compatibility debt such
   as the now five-line `page_preview_office.py` facade.

## 3. Exact malicious fixtures

Generate fixtures at test runtime under a disposable directory. Do not commit
opaque binary blobs. Keep the payload strings below verbatim in
`tests/browser/preview_fixture_factory.py` so both Python and Playwright can
assert the same markers.

### 3.1 PDF

Create a valid three-page PDF. Page 1 contains literal visible text:

```text
</span><img src=x onerror="parent.__maraPdfXss+=1"><script>parent.__maraPdfXss+=10</script><svg onload="parent.__maraPdfXss+=100">
```

Page 2 contains `MARA PDF PAGE TWO`; page 3 contains `MARA PDF PAGE THREE`.
Also add:

- a document JavaScript/OpenAction payload
  `app.launchURL('https://attacker.invalid/pdf-open', true)`;
- a URI annotation with
  `javascript:parent.__maraPdfXss+=1000`;
- a second URI annotation to
  `https://attacker.invalid/pdf-link`.

The test is successful only when PDF.js renders the literal page text, the
page/top URL does not navigate, no popup or dialog appears, no request reaches
`attacker.invalid`, and `window.__maraPdfXss` stays `0`.

### 3.2 DOCX

Create a valid DOCX with these package elements:

- a normal paragraph `MARA DOCX SAFE TEXT`;
- literal text
  `<img src=x onerror="parent.__maraDocxXss+=1"><script>parent.__maraDocxXss+=10</script>`;
- external hyperlink text `DOCX JS LINK` whose relationship target is
  `javascript:parent.__maraDocxXss+=100`;
- external hyperlink text `DOCX HTTP LINK` whose target is
  `https://attacker.invalid/docx-link`;
- an embedded `word/media/evil.svg` with content type `image/svg+xml` and body
  `<svg xmlns="http://www.w3.org/2000/svg" onload="parent.__maraDocxXss+=1000"><script>parent.__maraDocxXss+=10000</script></svg>`;
- image alt text
  `"><img src=x onerror="parent.__maraDocxXss+=100000">`.

The rich preview must keep both text labels, render `DOCX JS LINK` without an
`href`, omit the SVG data URL, create no active node, and keep the parent marker,
popup count, attacker request count, and top navigation count at zero.

### 3.3 PPTX

Create a valid two-slide PPTX. Slide 1 contains:

- text
  `</p><img src=x onerror="parent.__maraPptxXss+=1"><script>parent.__maraPptxXss+=10</script>`;
- run `PPTX JS LINK` with hyperlink
  `javascript:parent.__maraPptxXss+=100`;
- run `PPTX HTTP LINK` with hyperlink
  `https://attacker.invalid/pptx-link`;
- an image relationship whose declared content type is `image/svg+xml` and
  whose bytes are
  `<svg xmlns="http://www.w3.org/2000/svg" onload="parent.__maraPptxXss+=1000"><script>parent.__maraPptxXss+=10000</script></svg>`.

Slide 2 contains `MARA PPTX SLIDE TWO`. The renderer must keep the visible text,
render the JavaScript link as inert text, reject SVG as an embedded image MIME,
and preserve slide navigation without any marker, request, popup, form, or top
navigation side effect.

### 3.4 Assistant answer

Use this exact Markdown answer through the real answer-rendering path:

```text
<img src=x onerror="window.__maraAnswerXss+=1">
<script>window.__maraAnswerXss+=10</script>
[JS LINK](javascript:window.__maraAnswerXss+=100)
![SVG IMAGE](data:image/svg+xml,<svg onload="window.__maraAnswerXss+=1000"></svg>)
[DATA HTML](data:text/html,<script>window.__maraAnswerXss+=10000</script>)
</summary></details><form action="https://attacker.invalid/answer-form"><button autofocus onfocus="window.__maraAnswerXss+=100000">submit</button></form>
Math: $\\href{javascript:window.__maraAnswerXss+=1000000}{click}$
```

After Markdown and KaTeX rendering, the visible labels remain, while scripts,
event attributes, forms, unsafe `href`/`src`, and active SVG are absent. Marker,
popup, dialog, external request, and navigation counters remain zero.

## 4. Real browser harness and flows

Add `tests/browser/serve_preview_flow.py` and
`tests/browser/preview_flow.spec.mjs`. Keep the existing Task 4 smoke unchanged.
The new server must launch a small real Gradio Blocks app using production:

- `ChatPanel` preview components and element IDs;
- `ChatPagePreviewController` (or its Task 12D compatibility facade);
- `chat_preview_events` and named adapter ports;
- composed `safe_dom.js`, `main.js`, and `pdf_viewer.js`;
- the packaged PDF.js materializer and actual `6.1.200` runtime;
- the real DOCX/PPTX renderers and typed preview payload builder.

Only index/source lookup and converter timing may be deterministic test doubles.
The harness must expose a real `gr.File` upload and the real source selector;
Playwright uses `setInputFiles`, waits for the uploaded source to appear, and
selects it. It must not assign the hidden preview-source field directly.

Register `page.addInitScript` markers for PDF, DOCX, PPTX, and answer payloads.
Also record `page.on('popup')`, `page.on('dialog')`, top-frame navigations, form
submissions, console errors, and every request whose host is
`attacker.invalid`.

Required flows:

1. **Malicious binary files:** upload the generated PDF/DOCX/PPTX files one at
   a time, select each through the source selector, wait for its real iframe,
   inspect its DOM/policy, attempt to activate every rendered link/button, and
   assert all side-effect counters remain zero.
2. **Normal PDF navigation:** upload/select the three-page PDF, wait for
   `PDFViewerApplication.initializedPromise`, assert page 1, click Next and
   assert page 2, set the page-number input to 3 and assert page 3, then test
   lower/upper clamp. The same iframe/document remains mounted for same-document
   jumps. Its URL keeps `embed=1`, `disablehistory=true`,
   `sidebarviewonload=0`, `ktempage`, `ktemfit=pdf`, encoded same-origin
   `file=`, and matching `#page=`.
3. **Office same-page polling:** upload a normal DOCX whose text deterministically
   paginates to three placeholder pages, select it, navigate its placeholder to
   page 2, and let a delayed deterministic converter publish a valid three-page
   PDF. The active four-output timer callback replaces the placeholder with
   PDF.js using `ktemfit=office` while
   both the Gradio page input and `PDFViewerApplication.page` remain `2`.
   The conversion runs once and PDF.js is neither materialized nor rewritten
   during selection or polling.
4. **Corrupt Office diagnostics:** upload a corrupt DOCX and corrupt PPTX whose
   filenames and parse reasons include
   `<img src=x onerror="window.__maraNoticeXss=1">`. The visible notice contains
   the stable typed code/stage/converter as escaped text, no active node exists,
   and the server log contains the same structured diagnostic.
5. **Answer rendering:** send the exact hostile answer through the production
   answer renderer/UI output and assert the answer-specific conditions from
   section 3.4 after KaTeX processing.

The deterministic converter closes the UI/polling contract without making the
browser gate depend on LibreOffice availability. Existing Office core tests
remain responsible for real subprocess command/output behavior.

## 5. Source, image, iframe, and CSP policy

### 5.1 Preview-source allowlist

Move source classification into testable `safe_dom.js` functions used by
`main.js`:

- accept PDF.js only when origin and pathname exactly match the injected
  packaged viewer path;
- require its `file` query value to be same-origin and under Gradio's `/file=`
  route; reject credentials, protocol-relative URLs, backslashes, encoded
  traversal, duplicate `file` parameters, and non-HTTP(S) schemes;
- accept document HTML only from the server-generated data-HTML contract;
  reject raw `<html...` hidden-state values;
- accept embedded images only as base64 `image/png`, `image/jpeg`, `image/gif`,
  or `image/webp`; reject SVG and generic `data:image*`;
- reject external image URLs and any preview source that is not the exact
  PDF.js URL, a locked document page, or an allowlisted image.

The current browser-forgeable `ktem-scripted=1` marker must not grant script
execution. Remove the PPTX inline script and run its resize/Ctrl-wheel zoom from
the trusted parent `main.js` after iframe load. All DOCX/PPTX/text document
frames can then use the non-scripted document policy.

When decoding a data-HTML value, `main.js` must construct/prepend the locked
document shell and CSP itself before assigning `srcdoc`; it must not trust a
marker or a `<meta>` supplied by the hidden field. The server-generated CSP may
remain for defense in depth, but client tampering cannot remove the parent-built
policy.

### 5.2 Exact iframe policy

- PDF.js frame: sandbox exactly `allow-scripts allow-same-origin` and
  `referrerpolicy="no-referrer"`. No forms, popups, downloads, modals,
  presentation, or top-navigation tokens.
- DOCX/PPTX/text frame: sandbox exactly `allow-same-origin` and
  `referrerpolicy="no-referrer"`; no `allow-scripts`.
- Unknown/invalid source: remove both `src` and `srcdoc` and show the inert empty
  state.

Every server-generated document page includes this effective CSP before any
document content:

```text
default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; form-action 'none'
```

Do not edit the verified upstream PDF.js archive to add policy. PDF.js keeps
the exact pinned asset tree and relies on the exact-viewer check plus its
minimal sandbox. Playwright must assert both policies from the rendered frame,
not merely grep source strings.

## 6. Precise Gradio `allowed_paths`

Create one shared helper used by both `launcher.launch_app` and
`sso.create_sso_app`. Its preview-relevant roots are exactly:

1. the verified version directory
   `KH_APP_DATA_DIR/assets/pdfjs/6.1.200` (the whole version root is required
   because viewer modules, worker, locale, fonts, images, and maps load beneath
   it);
2. the dedicated visible cache `GRADIO_TEMP_DIR/pdf_previews`, containing only
   validated PDF copies and canonical-to-visible Office artifacts.

Do not allow the canonical Office cache, the whole `GRADIO_TEMP_DIR`, or the
whole `KH_FILESTORAGE_PATH`. Original PDF sources must first be published to the
dedicated visible cache with a signature-safe name; Office keeps the documented
`<stem>_<legacy-md5[:12]>.pdf` visible filename ABI.

Non-preview UI assets may add only their actual roots: `ICONS_DIR` and the
configured Help `KH_DOC_DIR`. Replace broad `ASSETS_DIR` with `ICONS_DIR`; the
vendored PDF.js ZIP, manifests, JS sources, and unrelated package files must not
be reachable through Gradio's file route.

Python integration tests must assert the exact list for local/password and SSO
launch and make real HTTP requests proving these siblings are denied:

- `KH_APP_DATA_DIR/private.txt`;
- `KH_APP_DATA_DIR/assets/pdfjs/other-version/secret.txt`;
- `GRADIO_TEMP_DIR/secret.txt` outside `pdf_previews`;
- `KH_FILESTORAGE_PATH/victim.pdf`;
- the canonical Office cache artifact before its validated visible publish.

The same tests prove a PDF.js module/worker and a validated preview PDF remain
servable. A materializer spy raises if any preview callback calls it after app
startup, and viewer inode/mtime values remain unchanged across all browser
flows.

## 7. Typed render errors and decomposition

Use the existing `PreviewError` data contract. Malformed inputs raise
`PreviewSourceError`; missing renderer/converter dependencies and failed
conversion remain `PreviewConversionError`. Do not invent string-only render
exceptions. Required stages/converters are:

- PDF parse/page: `stage="pdf_validation"`, `converter="pypdf"`;
- DOCX package/render: `docx_package` or `docx_render`, `python-docx`;
- PPTX package/render: `pptx_package` or `pptx_render`, `python-pptx`;
- XLSX package/render: `xlsx_package` or `xlsx_render`, `ooxml`;
- HTML payload construction: `preview_html`, `internal-html`;
- PDF.js unavailable: `pdfjs_runtime`, `pdfjs-6.1.200`.

At the Web compatibility boundary, catch `PreviewError` only, log
`code/stage/source_path/converter/details`, and return an escaped actionable
notice. Filenames, paths, converter stderr, relationship targets, and parse
reasons are attacker-controlled and must pass through `html.escape(..., quote=True)` before notice HTML.

Split by responsibility while preserving import paths:

- `page_preview.py` remains the `ChatPagePreviewController` compatibility
  facade and documented method-name owner;
- move selected-file/page-set/page-delta/refresh/tick state transitions to a
  navigation service;
- keep routing in `page_preview_service.py` and split the current 103-line
  Office handler into placeholder, ready-PDF, and diagnostic helpers;
- split PPTX package parsing, safe HTML rendering, and style extraction into
  focused modules; enforce hyperlink schemes `http`, `https`, and `mailto`, and
  image MIME `png/jpeg/gif/webp` only;
- make PDF/page/source helpers delegate to the Task 12 shared core instead of
  reopening files through legacy `pypdf` code.

After the split, every touched preview module is <=600 lines, class <=300,
function <=80, and preview modules contain zero silent/non-actionable broad
exceptions. Optional imports catch `ImportError`; malformed archives/XML and
library operations use explicit exception tuples and translate to typed errors.
Do not grow or refresh `scripts/codebase_hygiene_baseline.json`. Remove or
downshift only entries proven lower by the final code, including stale entries
for the completed `page_preview_office.py` facade. Do not touch unrelated
`ChatPage` baseline debt.

## 8. ABI and event invariants

Refactoring and timer activation must preserve:

- selected-file callback: 3 component inputs, 14 outputs in the current order;
- prev/next/page-set navigation: 5 component inputs, 10 outputs;
- refresh-selected-preview: 4 inputs, 7 outputs;
- timer callback: existing direct-call 7 inputs plus legacy/timer-injected 8
  inputs, exactly 4 outputs, with no context/thumbnail tail;
- clear-page outputs: exactly 6 values;
- conversation preview: 4 inputs, 7 outputs;
- selected, prev, next, and page-set chains remain handler -> clear selection
  -> refresh context -> PDF JS;
- conversation restore remains selection -> plot -> visibility/suggestions ->
  preview -> context -> clear selection -> PDF refresh -> answer/question ->
  citations -> trace -> focus, with each `.then/.success` retaining its current
  parent.

No `gr.Request` may become a component input. Preserve direct-call sentinels,
component attributes/IDs, `ktemfit=pdf|office`, PDF.js query/hash fields, CLI,
JSON/DB/session shapes, and all old preview/re-export import paths.

To make the documented Office flow real without changing ports, activate the
existing timer and keep the current cheap early returns for no file, PDF, and
text sources. Do not add the Timer as a fifteenth selected-file output or a
fifth timer output.

## 9. Tests and gates

### 9.1 RED order

1. Add generated fixture and Python renderer/error tests. Confirm PPTX unsafe
   hyperlink/MIME, unescaped notice, silent corrupt render, and broad-catch
   ratchet cases fail for the intended reason.
2. Add exact allowed-path tests for both launch modes and real denied/allowed
   file-route requests. Confirm the current broad roots fail.
3. Add Node source-policy/CSP tests. Confirm raw HTML, forged scripted marker,
   SVG data, and malformed PDF.js URLs are accepted before production changes.
4. Add Playwright real-flow tests and confirm the missing Gradio harness/flow or
   unsafe behavior causes RED. Commit all security RED tests before production.

### 9.2 Focused local Python gate

```bash
KH_APP_DATA_DIR="$HOME/fastscratch/mara_runtime/task12d-tests" \
UV_NO_SYNC=1 uv run --no-sync pytest -q \
  libs/ktem/ktem_tests/test_dom_xss_contract.py \
  libs/ktem/ktem_tests/test_render_security.py \
  libs/ktem/ktem_tests/test_pdfjs_assets.py \
  libs/ktem/ktem_tests/test_pdfjs_integration_contract.py \
  libs/ktem/ktem_tests/test_preview_pdf_core.py \
  libs/ktem/ktem_tests/test_preview_pdf_compatibility.py \
  libs/ktem/ktem_tests/test_preview_docx_core.py \
  libs/ktem/ktem_tests/test_preview_docx_compatibility.py \
  libs/ktem/ktem_tests/test_preview_office_core.py \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py \
  libs/ktem/ktem_tests/test_preview_context_service.py \
  libs/ktem/ktem_tests/test_chat_gradio_preview_adapter.py \
  libs/ktem/ktem_tests/test_chat_gradio_conversation_adapter.py \
  libs/ktem/ktem_tests/test_chat_preview_timer.py
```

Append the new responsibility-specific test modules to this command. Do not
grow a test file beyond 600 lines merely to avoid creating a focused module.

### 9.3 Local frontend/browser gate

Reuse the installed locked Node tree and cached Chromium; do not run `npm ci`
or download a second browser merely for local Task 12D verification:

```bash
node --test libs/ktem/ktem/assets/js/*.test.js
PLAYWRIGHT_BROWSERS_PATH="$XDG_CACHE_HOME/ms-playwright" \
  ./node_modules/.bin/playwright test \
  --config tests/browser/playwright.config.mjs
```

Run Playwright traces/screenshots only on failure and store disposable output
under node-local `/tmp`; remove it after diagnosis. The local run is valid only
when the expected cached Chromium executable exists.

### 9.4 Hygiene and relevant regression

Run changed-file pre-commit, full `scripts/check_codebase_hygiene.py`,
`scripts/check_hygiene_baseline.py` against the trusted base, Ruff, mypy,
`git diff --check`, the relevant ktem preview/DocQA/file-index gate from the
final Task 12C report, and `uv lock --check`. Record exact baseline removals and
remaining large-code exceptions; never regenerate the baseline wholesale.

### 9.5 Hosted-CI-only evidence

The required `frontend-browser` job must perform the clean locked install and
system browser setup that local inode constraints should avoid:

```bash
npm ci --ignore-scripts
node --test libs/ktem/ktem/assets/js/*.test.js
./node_modules/.bin/playwright install --with-deps chromium
./node_modules/.bin/playwright test --config tests/browser/playwright.config.mjs
npm audit --audit-level=high
```

CI must run all existing Task 4 smokes plus the new binary-upload preview flow;
it may not replace them with source-grep assertions. Hosted Python 3.11,
complete ktem, clean-wheel PDF.js materialization, and required-summary status
remain CI evidence. A real LibreOffice browser conversion is optional nightly
evidence only; deterministic conversion in the required browser gate plus the
existing real Office core tests is the required PR contract.

## 10. Completion report

The Task 12D report must include RED/GREEN commits, exact malicious payloads,
browser action/assertion counts, local and CI-only commands, PDF.js archive and
runtime invariants, final allowed-path list, public/Gradio ABI impact, typed
error stages, baseline downshifts, storage/quota state, and residual risk. Do
not claim full-app browser coverage if only the focused Gradio preview harness
ran; state that boundary explicitly.
