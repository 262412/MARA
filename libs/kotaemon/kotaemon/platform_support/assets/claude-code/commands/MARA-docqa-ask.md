---
description: Ask one question through MARA DocQA
argument-hint: [question]
allowed-tools: Bash(MARA:*)
---

Ask one MARA DocQA question.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`MARA docqa doctor`
2. If needed, scope retrieval with `--file`, `--page`, or `--selected-text`.
3. Run:
   !`MARA docqa ask --prompt "$ARGUMENTS"`
