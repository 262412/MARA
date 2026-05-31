---
description: Search slide decks and slide content
argument-hint: [query] [paths...]
allowed-tools: Bash(MARA:*)
---

Search slide decks and slide content.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA search $ARGUMENTS`
