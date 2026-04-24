---
description: Extract slide deck content or assets
argument-hint: [deck path] [extract args]
allowed-tools: Bash(slide:*)
---

Extract slide content or assets.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide extract $ARGUMENTS`
