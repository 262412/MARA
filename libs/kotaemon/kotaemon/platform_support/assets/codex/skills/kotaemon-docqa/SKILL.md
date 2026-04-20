---
name: kotaemon-docqa
description: This skill should be used when the user wants document QA, document indexing, or sessioned document chat through Kotaemon CLI while preserving the same QA flow as the app.
version: 1.0.0
---

# Kotaemon DocQA (Codex)

Use natural-language prompts by default.
Use explicit invocation with `$kotaemon-docqa` when the user wants deterministic CLI-backed document QA.

## Workflow

1. Run `kotaemon docqa doctor` before the first QA turn in a fresh environment.
2. If files are not indexed yet, run `kotaemon docqa index ...`.
3. Inspect indexed files with `kotaemon docqa files` when scope is unclear.
4. Use `kotaemon docqa ask --prompt "..."` for one-shot QA.
5. Use `kotaemon docqa chat` or `kotaemon docqa resume <conversation-id>` for multi-turn sessions.

## Command Set

- `kotaemon docqa doctor`
- `kotaemon docqa index <path...> [--reindex]`
- `kotaemon docqa files`
- `kotaemon docqa ask --prompt "..."`
- `kotaemon docqa chat`
- `kotaemon docqa sessions`
- `kotaemon docqa resume <conversation-id>`

## Quality Gates

- `doctor` reports a healthy runtime and a default file index.
- Indexed files appear in `files`.
- `ask` or `chat` returns an answer and evidence.
- Conversation ids from CLI can be resumed later.
