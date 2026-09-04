# Task 12D Completion Report

Date: 2026-07-12

Status: complete with documented framework and architecture residuals

Commit range: `32eaac8..0f02dc9`

## Outcome

The browser preview boundary now accepts only the exact same-origin packaged
PDF.js viewer, locked percent-encoded document HTML, and base64 PNG/JPEG/GIF/
WebP images. Raw HTML, forged scripted-document markers, SVG data, external
images, duplicate or cross-origin PDF `file` parameters, credentials,
backslashes, and encoded traversal fail closed. Document frames have no script
capability; PDF.js receives exactly `allow-scripts allow-same-origin`; both use
`referrerpolicy=no-referrer`.

Gradio file-serving roots are centralized and reduced to icons, the verified
PDF.js 6.1.200 version root, configured Help docs, and `pdf_previews`. Original
PDFs are copied atomically to signature-qualified visible names so equal
basenames cannot collide. File storage, the app-data root, and other PDF.js
versions are not allowlisted. Local/password and SSO launchers share the same
helper.

PPTX JavaScript hyperlinks are rendered as inert text, hyperlinks use only
http/https/mailto, embedded images require an allowlisted MIME and matching
binary signature, inline PPTX scripts were removed, and zoom runs from the
trusted parent. Preview notices HTML-escape attacker-controlled details. The
Office timer is active and PDF.js same-document page changes use the live
viewer application without remounting the iframe.

## Real browser boundary

The focused Gradio Blocks harness uses the production ChatPanel preview DOM,
source selector, hidden preview port, safe DOM/main scripts, PDF.js
materializer/runtime, DOCX renderer, PPTX renderer, notice builder, and PDF
viewer URL builder. Only source indexing and Office conversion timing are not
the full application implementation.

Generated fixtures contain the specified PDF/DOCX/PPTX hostile markup,
JavaScript and HTTP links, SVG package parts, three PDF pages, two PPTX slides,
and corrupt Office inputs. No opaque binary fixture is committed.

The final Chromium run executed eight cases:

- 1 exact file-route isolation case covering three denied sibling roots;
- 1 malicious PDF upload/PDF.js render and same-iframe page 1→2→3 flow;
- 2 malicious DOCX/PPTX upload and document-sandbox flows;
- 2 corrupt DOCX/PPTX escaped-diagnostic flows;
- 1 hostile text/highlight/sandbox smoke;
- 1 exact hostile assistant-answer production renderer smoke.

All XSS markers, popup/dialog counters, and attacker-host request counters
remained zero in the malicious binary flows.

## Compatibility and public surface

- `MARA`, `MARA-cli`, DB/JSON/session schemas, preview component IDs, callback
  ports, output counts, and event-chain order are unchanged.
- The PDF.js archive remains version 6.1.200 with SHA-256
  `9e1584d768ed099aa4be27ea423f89a038c2005f1ee417ea4f35ba4591ec1846`;
  no archive file was edited.
- Original PDF visible-cache filenames intentionally gain a source-signature
  suffix. The established Office visible PDF filename ABI remains unchanged.
- The preview Timer changes from inactive to active at its existing two-second
  interval; its seven inputs and four outputs are unchanged.

## Verification

- Node source-policy/DOM suite: `18 passed`.
- Focused preview Python gate: `151 passed, 6 warnings`.
- Focused renderer compatibility gate: `81 passed, 6 warnings`.
- Real Chromium gate: `8 passed in 17.4s`.
- Final full ktem gate: `1200 passed, 46 warnings in 33.74s`.
- `uv lock --check --offline`: 403 packages resolved, exit 0.
- Full hygiene and baseline-widening guard against `e169cf2`: green.
- All changed-file pre-commit hooks and `git diff --check`: green.

## Baseline debt

- Removed stale entries for the five-line Office facade, resolver, runtime,
  spreadsheet, text, and type modules.
- `page_preview.py`: 844→828 module lines, controller 790→772,
  `on_page_change` 97→94, `on_page_set` 86→83, broad exceptions 1→0.
- `page_preview_presentation.py`: 524→495 module lines, class 483→453,
  broad exceptions 17→15.
- No allowance increased or regenerated.

## Storage and residual risk

- Browser and Python runtime roots were under `/tmp/mara-preview-browser` and
  `/mnt/fastscratch/users/tbczhang/mara_runtime`; no live MARA DB was selected.
- Gradio 4.39 automatically serves files in its framework upload directory
  (`GRADIO_TEMP_DIR`) independently of `allowed_paths`. Therefore that root
  must remain an isolated, non-secret upload/cache directory. App data,
  file-storage data, and unrelated PDF.js versions are denied and were verified
  by real HTTP requests.
- The browser harness proves placeholder and final renderer boundaries but does
  not run a deterministic delayed LibreOffice replacement through the full
  ChatPage timer. Python timer/Office conversion suites own that path.
- `ChatPagePreviewController` (772 lines) and
  `PresentationPreviewService` (453 lines, 15 broad catches) remain above the
  architectural target despite measurable reductions. They are explicit
  maintenance debt, not an unresolved active-content boundary.
- Existing framework and parser deprecation warnings remain non-blocking.

Task 12D security verdict: **COMPLETE**. Remaining items are maintenance and
framework-hardening follow-ups recorded for the final risk report.
