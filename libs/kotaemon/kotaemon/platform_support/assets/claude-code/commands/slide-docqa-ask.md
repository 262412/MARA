---
description: Ask one question through slide DocQA
argument-hint: [question]
allowed-tools: Bash(slide:*)
---

Ask one slide DocQA question.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`slide docqa doctor`
2. If needed, scope retrieval with `--file`, `--page`, or `--selected-text`.
3. Run:
   !`slide docqa ask --prompt "$ARGUMENTS"`
