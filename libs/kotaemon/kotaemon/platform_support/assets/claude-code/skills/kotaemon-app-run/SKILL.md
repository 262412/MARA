---
name: kotaemon-app-run
description: Use this skill to launch the packaged Kotaemon Web UI.
version: 1.0.0
---

# Kotaemon App Run

## Scope

Use this skill to launch the packaged Web UI without the source repository.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon app doctor`
- `kotaemon app run`

## Relevant Parameters

- `--host <host>`
- `--port <port>`
- `--share`
- `--no-browser`
