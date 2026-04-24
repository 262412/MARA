---
description: Run slide-focused document QA workflows
argument-hint: [question]
allowed-tools: Bash(slide:*)
---

Run slide-focused document QA through `slide docqa ...`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`slide docqa doctor`
2. If the user names files, index missing files first:
   !`slide docqa index $ARGUMENTS`
3. For one-shot QA, run:
   !`slide docqa ask --prompt "$ARGUMENTS"`
4. For multi-turn work, use:
   !`slide docqa chat`
5. Prefer focused wrappers when intent is specific:
   - `slide-docqa-doctor`
   - `slide-docqa-index`
   - `slide-docqa-files`
   - `slide-docqa-delete`
   - `slide-docqa-ask`
   - `slide-docqa-chat`
   - `slide-docqa-sessions`
   - `slide-docqa-resume`
