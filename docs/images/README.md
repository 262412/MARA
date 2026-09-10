# README screenshots

## Web startup capture

- `mara-web-start.png`: real Web workbench captured on 2026-09-10 from source
  checkout `412568ed`, using the existing Windows Python environment.
- Launch command: `MARA app run --host 127.0.0.1 --port 7876 --no-browser`.
- A separate temporary runtime was used, with no configured model and no
  imported user documents. The visible version label comes from the locally
  installed distribution metadata.
- This image demonstrates startup and layout only. It is not evidence of
  successful indexing, model inference, citations, or artifact generation.

## Real document QA and Desktop captures

The user provided these two screenshots on 2026-09-10 for inclusion in both
READMEs. Their capture dates and source commits were not supplied.

- [mara-web-evidence.webp](mara-web-evidence.webp): the Web workbench with
  `Research Project.docx` indexed, page navigation, a source preview, and an
  answer panel. `Document` scope is selected; the visible answer is headed
  `Summary of Page 1`. The footer displays version `0.0.18`.
- [mara-desktop-workspace.webp](mara-desktop-workspace.webp): the native Desktop
  workbench with recent tasks, a document summary containing inline reference
  markers, and the selected source in the Sources panel. The answer is still
  marked `Generating`; this capture illustrates streaming, not a completed task.

Both images preserve the original 2559 x 1551 dimensions and were encoded as
lossless WebP to meet the repository's 750 KiB per-file limit. Decoded pixels
were checked against the supplied PNG files and match exactly.

The remaining images in this directory predate this README rewrite and are
retained for existing documentation references.

## Useful follow-up capture

A completed Studio study guide or quiz, showing its source and export control,
would extend the walkthrough. A suggested filename is `mara-studio-result.png`.
Use public or fictional source documents and exclude credentials and personal
document content.

Keep the release/commit, source document, capture date, and demonstrated result
with each replacement. Add the image to both READMEs only after it exists;
avoid broken-image placeholders.
