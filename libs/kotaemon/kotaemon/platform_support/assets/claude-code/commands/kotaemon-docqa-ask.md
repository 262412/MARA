---
description: Run one DocQA question through the shared CLI
argument-hint: [question]
allowed-tools: Bash(kotaemon:*)
---

Run one DocQA question.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Validate the runtime first:
   !`kotaemon docqa doctor`
2. If the user names files, scope retrieval with `--file`.
3. If the user asks about one page only, add `--page <n>`.
4. If the user gives an exact snippet, add `--selected-text "..."`.
5. Run:
   !`kotaemon docqa ask --prompt "$ARGUMENTS"`
