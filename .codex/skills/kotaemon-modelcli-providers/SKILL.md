---
name: kotaemon-modelcli-providers
description: Use this skill to inspect model routing provider availability.
version: 1.0.0
---

# Kotaemon ModelCLI Providers

## Scope

Use this skill to inspect provider availability before running routed model calls.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon modelcli providers --config modelcli.yml`

## Relevant Parameters

- `--config <path>`

## Quality Gates

- The expected provider reports as available before network calls.
