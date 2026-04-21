---
name: kotaemon-docqa-resume
description: Use this skill to reopen a saved DocQA conversation in the REPL.
version: 1.0.0
---

# Kotaemon DocQA Resume

## Scope

Use this skill to reopen an existing conversation with `kotaemon docqa resume`.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa sessions`
- `kotaemon docqa resume <conversation-id>`

## Relevant Parameters

- `<conversation-id>` comes from `kotaemon docqa sessions`
- `--json` emits structured output for each reply in the REPL

## Quality Gates

- Resume only uses an existing conversation id.
- The reopened session preserves prior history.
