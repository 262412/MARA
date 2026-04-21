---
name: kotaemon-docqa-doctor
description: Use this skill to validate DocQA runtime health before working with documents.
version: 1.0.0
---

# Kotaemon DocQA Doctor

## Scope

Use this skill to validate DocQA runtime, index, and session prerequisites.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa doctor`

## Relevant Parameters

- `--json` emits structured output

## Quality Gates

- Runtime reports `OK`.
- Any issues or warnings are surfaced before later DocQA commands run.
