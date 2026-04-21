---
name: kotaemon-docqa-files
description: Use this skill to inspect indexed files in the shared DocQA collection.
version: 1.0.0
---

# Kotaemon DocQA Files

## Scope

Use this skill to list indexed files and collect file ids or names for later commands.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa files`

## Relevant Parameters

- `--json` emits structured output

## Quality Gates

- Returned file ids or names are reused in `ask`, `delete`, or `chat` commands.
