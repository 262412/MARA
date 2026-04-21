---
name: kotaemon-docqa-chat
description: Use this skill to start or continue an interactive DocQA chat session.
version: 1.0.0
---

# Kotaemon DocQA Chat

## Scope

Use this skill to open the interactive DocQA REPL backed by saved conversation state.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa doctor`
- `kotaemon docqa chat`

## Relevant Parameters

- `--conversation <conversation-id>` to continue a saved conversation
- `--file <file-id-or-name>` to scope retrieval
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

## REPL Commands

- `/files`
- `/use <file>`
- `/page <n>`
- `/page clear`
- `/selected-text <text>`
- `/history`
- `/exit`

## Quality Gates

- `doctor` succeeds before the first chat run in a fresh environment.
- Sessions remain resumable through `kotaemon docqa resume`.
