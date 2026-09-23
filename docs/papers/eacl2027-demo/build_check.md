# Build and verification

- Compiled with TeX Live 2025 / latexmk, pdfLaTeX and BibTeX. Build command,
  source/PDF digests and log are recorded in paper_state.json.
- PDF: 13 pages; substantive content ends on page 6. References and informative
  appendices follow. Original ACL styles, font sizes and margins are preserved.
- Four authors and affiliation retained; the title page has no email.
- Figure 2 is a vector diagram of the recorded case. PDF layout is rendered and
  inspected; no overfull boxes or unresolved references/citations are reported.
- The Overleaf ZIP compiles after extraction; extracted PDF text matches the
  primary build. Overleaf cloud compilation itself is not claimed.
- The supplementary ZIP's offline verifier passes after extraction. New case
  records retain the negative independent repetition and exclude credentials.
- Real execution of the supplied case script in an empty runtime completed;
  it produced the retained negative repetition, not an assumed successful repair.
- Python artifact scripts pass codebase hygiene and pre-commit checks. The app
  source/public CLI is unchanged, so no application-wide test suite was rerun.
- The numeric registry passes against released summary tables and audit values.
  Existing scholarly references are retained; this revision does not claim a new
  independent bibliographic audit or a terminal citation-lock certification.

Detailed records: audit/diagnostic-case-verification.json and
audit/diagnostic-package-check.json. The original video, historical synthesis,
submitted PDF and primary refactor checkout are preserved.
