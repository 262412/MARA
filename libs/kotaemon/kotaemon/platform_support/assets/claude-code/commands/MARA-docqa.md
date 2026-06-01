---
description: Run MARA-focused document QA workflows
argument-hint: [question]
allowed-tools: Bash(MARA:*)
---

Run MARA-focused document QA through `MARA docqa ...`.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the DocQA runtime first:
   !`MARA docqa doctor`
2. If the user names files, index missing files first:
   !`MARA docqa index $ARGUMENTS`
3. For one-shot QA, run:
   !`MARA docqa ask --prompt "$ARGUMENTS"`
4. For multi-turn work, use:
   !`MARA docqa chat`
5. Prefer focused wrappers when intent is specific:
   - `MARA-docqa-doctor`
   - `MARA-docqa-index`
   - `MARA-docqa-files`
   - `MARA-docqa-delete`
   - `MARA-docqa-ask`
   - `MARA-docqa-chat`
   - `MARA-docqa-sessions`
   - `MARA-docqa-notes`
   - `MARA-docqa-sources`
   - `MARA-docqa-artifacts`
   - `MARA-docqa-resume`
