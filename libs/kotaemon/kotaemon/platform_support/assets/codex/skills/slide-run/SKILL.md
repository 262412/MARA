---
name: slide-run
description: Use this skill to run the top-level slide agent with `slide run`.
version: 1.0.0
---

# Slide Run

## Scope

Use this skill for a single top-level slide rewrite task.

## Command

- `slide run`

## Relevant Parameters

- `--file <path>` selects the source deck
- `--prompt "..."` supplies the instruction
- `--output <path>` writes the result to a specific file
- `--apply` applies the generated patch to a deck copy
- `--dry-run` previews without writing a new deck
- `--model <name>` overrides the default model
- `--provider <name>` overrides the provider
- `--config <path>` points at the runtime config
- `--cwd <path>` sets working-directory context
- `--approval-policy auto|confirm` controls write approvals
- `--shell-timeout <seconds>` sets the shell timeout
- `--max-iterations <n>` limits agent steps
- `--json` emits structured output

Use `slide apply` when the task is specifically to apply an existing patch, and `slide review` for read-only review work.
