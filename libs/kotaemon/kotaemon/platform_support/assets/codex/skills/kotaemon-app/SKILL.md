---
name: kotaemon-app
description: Use this skill for packaged app setup, inspection, and launch workflows.
version: 1.0.0
---

# Kotaemon App

## Scope

Use this skill for packaged app workflows through `kotaemon app ...`.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command Set

- `kotaemon app init`
- `kotaemon app doctor`
- `kotaemon app run`

## Focused Action Skills

- `kotaemon-app-init`
- `kotaemon-app-doctor`
- `kotaemon-app-run`

Use this umbrella skill when the user needs more than one app action in one workflow.
