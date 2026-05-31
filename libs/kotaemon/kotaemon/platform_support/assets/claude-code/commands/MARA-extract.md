---
description: Extract slide deck content or assets
argument-hint: [deck path] [extract args]
allowed-tools: Bash(MARA:*)
---

Extract slide content or assets.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA extract $ARGUMENTS`
