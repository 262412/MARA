---
description: Run Kotaemon document QA through the shared docqa CLI
argument-hint: [question]
allowed-tools: Bash(kotaemon:*)
---

Run a quick Kotaemon document QA workflow.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Validate the runtime first:
   !`kotaemon docqa doctor`

2. If the user names one or more files, scope retrieval with `--file`.

3. If the user asks about one page only, add `--page <n>`.

4. If the user gives an exact snippet to focus on, add `--selected-text "..."`.

5. Run the question through the shared DocQA pipeline:
   !`kotaemon docqa ask --prompt "$ARGUMENTS"`

6. If the user asks for an interactive or resumable session, use:
   !`kotaemon docqa chat`

Prefer the focused command wrappers when the user intent is specific:

- `kotaemon-docqa-ask`
- `kotaemon-docqa-index`
- `kotaemon-docqa-chat`
- `kotaemon-docqa-files`
- `kotaemon-docqa-delete`
- `kotaemon-docqa-sessions`
- `kotaemon-docqa-resume`
- `kotaemon-docqa-doctor`
- `kotaemon-docqa-acceptance`

If the collection is empty, index files first with `kotaemon docqa index ...`.

Available shared QA parameters:

- `--conversation <conversation-id>`
- `--file <file-id-or-name>` (repeatable)
- `--active-file <file-id-or-name>`
- `--page <n>`
- `--selected-text "..."`
- `--graph-context-file <path.json>`
- `--reasoning <reasoning-id>`
- `--llm <llm-name>`
- `--citation highlight|inline|off`
- `--language <language>`
- `--mindmap`
- `--json`
