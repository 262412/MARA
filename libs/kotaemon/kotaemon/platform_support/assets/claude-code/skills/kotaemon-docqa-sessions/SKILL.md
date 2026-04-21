---
name: kotaemon-docqa-sessions
description: Use this skill to inspect saved DocQA conversations.
version: 1.0.0
---

# Kotaemon DocQA Sessions

## Scope

Use this skill to list saved DocQA conversations and collect conversation ids.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa sessions`

## Relevant Parameters

- `--json` emits structured output

## Quality Gates

- Returned conversation ids are reused in `kotaemon docqa resume`.
