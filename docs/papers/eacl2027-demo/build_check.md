# Build and verification

- Compiled with TeX Live 2025, latexmk, pdfLaTeX and BibTeX. The executed
  command, source/PDF digests and log are recorded in paper_state.json.
- The current PDF has 14 pages; substantive content ends within page 6 and
  references begin on page 6. Original ACL styles, font sizes and margins are
  preserved. All fonts are embedded. All rendered pages were inspected; no
  clipping, overlapping elements, overfull boxes or unresolved citations were
  found. Figure 2 is the real NOAA/NASA page image used by the visual model.
- Four authors and affiliation are retained, with no email. The manuscript,
  PDF metadata and submission fields use LMDoc. MARA remains only where needed
  for actual release names, commands, paths, URLs, screenshots and raw evidence.
- The Overleaf ZIP contains 11 entries and compiles after extraction. Extracted
  PDF text matches the primary build. Overleaf cloud execution is not claimed.
- The supplementary ZIP contains 137 entries and is 2,886,773 bytes, below the
  100 MB limit. Both offline verifiers pass after extraction. The follow-up
  manifest validates 94 files; provider messages, answer stages, actual visual
  calls and image bytes are retained without credentials or runtime databases.
- The original case files and historical benchmark ZIP remain byte-identical.
  The latter's SHA-256 is
  `7fabae169ef270dd2e6ee5edd1aa74841f3ffa100f3bf47bb5fa6139f866cafb`.
- The supplied chart recipe was executed again in a fresh isolated runtime.
  It repeated the same task's text, image and image-removed observations; this
  is reproducibility evidence, not another independent task or automatic repair.
- The targeted verifier fix lives in the separate source worktree at commit
  `9472e9e19a598ef522acd52ad88aa08da6a666a5`, after a failing regression commit.
  The relevant verifier/controller suite passes 129 tests. Applying the bundled
  patch to clean base files reproduces the two repaired source files exactly.
  The published installer and primary checkout are unchanged.
- Changed Python files pass the codebase hygiene gate and formatting checks.
  In the repair worktree, default Windows mypy reports eight existing POSIX
  attribute errors in untouched files; the same hook's Linux-platform check
  passes for the two changed files. The paper's Python checks pass.
- Raw unified-diff context lines are deliberately excluded from generic
  whitespace rewriting. Two correct personal names in the existing
  bibliography trigger codespell false positives and are retained as written.
  All other applicable paper pre-commit checks pass.
- Numeric evidence selectors and the research quality gate pass. The new
  NOAA/NASA report metadata and page were verified against the official PDF;
  this revision does not claim a new complete scholarly citation-lock audit.
- Browser security policy blocked local HTML preview. Both offline viewers'
  contents and local links were checked, but browser visual review is not
  claimed. The PDF was rendered and visually inspected independently.

Detailed records are in audit/followup-verification.json,
audit/followup-package-verification.json and audit/source-patch-check.json.
Current deliverable hashes are in submission/followup-artifact-manifest.json.

Scientific limits remain explicit: no participant study or executed Kotaemon
baseline establishes easier diagnosis; the visual intervention is manual; the
targeted lexical fix does not establish general verifier reliability; historical
SlideVQA answers and executed generation paths remain unavailable. The original
video is unchanged. No external submission or release update was performed.

The subsequent prose revision preserves the numeric tables, bibliography,
figure pixels and all captured evidence. The abstract matches the submission
field. Harbor context now appears on page 4 before its inspection table on
page 5 (Table 3). Section 4 has separate verifier and visual subsections, and
the conclusion leads with demonstrated contributions. All 14 final pages were
visually checked again. Extracted-package compilation and both offline checks
pass; see audit/prose-revision-verification.json.
