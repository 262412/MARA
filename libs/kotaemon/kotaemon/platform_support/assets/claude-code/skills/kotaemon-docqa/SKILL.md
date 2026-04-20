---
name: kotaemon-docqa
description: This skill should be used when the user wants Kotaemon document QA, document indexing, or resumable document chat through the CLI while matching the app's QA flow.
version: 1.0.0
---

# Kotaemon DocQA

## Scope

Use this skill to drive Kotaemon document QA through `kotaemon docqa ...` commands.

## Core Workflow

1. Run `kotaemon docqa doctor` in a fresh environment.
2. Index missing documents with `kotaemon docqa index`.
3. Review the available collection with `kotaemon docqa files` if file scope matters.
4. Run `kotaemon docqa ask --prompt "..."` for a single QA turn.
5. Run `kotaemon docqa chat` or `kotaemon docqa resume <conversation-id>` for multi-turn work.

## Command Set

- `kotaemon docqa doctor`
- `kotaemon docqa index <path...> [--reindex]`
- `kotaemon docqa files`
- `kotaemon docqa delete <file-id-or-name>...`
- `kotaemon docqa ask --prompt "..."`
- `kotaemon docqa chat`
- `kotaemon docqa sessions`
- `kotaemon docqa resume <conversation-id>`

## Quality Gates

- `doctor` succeeds before running QA in a new workspace.
- Retrieval scope is explicit when the user names files.
- Answers include evidence output.
- Sessions remain resumable across CLI and app usage.
