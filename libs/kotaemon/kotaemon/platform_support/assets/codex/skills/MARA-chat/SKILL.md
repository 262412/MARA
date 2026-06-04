---
name: MARA-chat
description: Use this skill to start interactive top-level MARA chat with `MARA chat`.
version: 1.0.0
---

# MARA Chat

## Scope

Use this skill for interactive, multi-turn top-level slide agent work.

## Command

- `MARA chat`

## Relevant Parameters

- `--file <path>` selects the source deck
- `--prompt "..."` provides an optional first prompt
- `--model <name>` overrides the default model
- `--provider <name>` overrides the provider
- `--config <path>` points at the runtime config
- `--cwd <path>` sets working-directory context
- `--approval-policy auto|confirm` controls write approvals
- `--shell-timeout <seconds>` sets the shell timeout
- `--max-iterations <n>` limits agent steps
- `--json` emits structured output

If the user already has a saved session, prefer `MARA resume`.
