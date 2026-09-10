# README screenshots

## Current capture

- `mara-web-start.png`: real Web workbench captured on 2026-09-10 from source
  checkout `412568ed`, using the existing Windows Python environment.
- Launch command: `MARA app run --host 127.0.0.1 --port 7876 --no-browser`.
- A separate temporary runtime was used, with no configured model and no
  imported user documents. The visible version label comes from the locally
  installed distribution metadata.
- This image demonstrates startup and layout only. It is not evidence of
  successful indexing, model inference, citations, or artifact generation.
- The other images in this directory predate this README rewrite. They were
  retained for existing documentation references, but are not presented as
  new verification evidence.

## Useful follow-up captures

These images would improve the walkthrough when a configured demonstration
environment is available. Use public or fictional source documents and exclude
credentials and personal document content.

| Suggested filename           | What to show                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------------ |
| `mara-web-evidence.png`      | An imported PDF, a real question and answer, and the cited passage/page visible together   |
| `mara-studio-result.png`     | A completed study guide or quiz based on the selected source, including its export control |
| `mara-desktop-workspace.png` | The native Desktop application after file indexing and a completed conversation task       |

The browser workbench was captured in this update. A real-model answer and
Studio output were not generated in the empty capture environment.
The available browser automation does not capture native Electron windows,
so the Desktop image needs a native-app capture.

Keep the release/commit, source document, capture date, and demonstrated result
with each replacement. Add the image to both READMEs only after it exists;
avoid broken-image placeholders.
