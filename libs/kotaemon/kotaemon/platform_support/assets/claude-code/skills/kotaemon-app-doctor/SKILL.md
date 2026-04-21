---
name: kotaemon-app-doctor
description: Use this skill to inspect packaged app runtime health.
version: 1.0.0
---

# Kotaemon App Doctor

## Scope

Use this skill to inspect packaged runtime settings, paths, and DocQA readiness.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon app doctor`

## Relevant Parameters

- `--json`
