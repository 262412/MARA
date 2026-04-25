---
description: Search slide decks and slide content
argument-hint: [query] [paths...]
allowed-tools: Bash(slide:*)
---

Search slide decks and slide content.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide search $ARGUMENTS`
