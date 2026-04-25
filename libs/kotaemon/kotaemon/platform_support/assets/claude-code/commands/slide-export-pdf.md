---
description: Export slide decks to PDF
argument-hint: [deck path] [--output path]
allowed-tools: Bash(slide:*)
---

Export a slide deck to PDF.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide export-pdf $ARGUMENTS`
