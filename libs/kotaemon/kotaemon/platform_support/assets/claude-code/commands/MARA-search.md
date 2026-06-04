---
description: Search slide decks and slide content
argument-hint: [query] [paths...]
allowed-tools: Bash(MARA:*)
---

Search slide decks and slide content.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA search $ARGUMENTS`
