---
name: kotaemon-modelcli-init-config
description: Use this skill to generate a default `modelcli.yml` config.
version: 1.0.0
---

# Kotaemon ModelCLI Init Config

## Scope

Use this skill to generate a default runtime config for `modelcli`.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon modelcli init-config --output modelcli.yml`

## Relevant Parameters

- `--output <path>`
- `--force`
