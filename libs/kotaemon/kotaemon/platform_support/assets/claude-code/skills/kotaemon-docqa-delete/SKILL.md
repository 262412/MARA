---
name: kotaemon-docqa-delete
description: Use this skill to remove indexed files from the shared DocQA collection.
version: 1.0.0
---

# Kotaemon DocQA Delete

## Scope

Use this skill to delete indexed files by id or name.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa files`
- `kotaemon docqa delete <file-id-or-name>...`

## Relevant Parameters

- `<file-id-or-name>...` accepts one or more ids or file names
- `--json` emits structured output

## Quality Gates

- Use ids or names from `kotaemon docqa files`.
- Report exactly which files were deleted.
