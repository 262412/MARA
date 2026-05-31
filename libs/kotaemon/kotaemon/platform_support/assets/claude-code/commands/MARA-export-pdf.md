---
description: Export slide decks to PDF
argument-hint: [deck path] [--output path]
allowed-tools: Bash(MARA:*)
---

Export a slide deck to PDF.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA export-pdf $ARGUMENTS`
