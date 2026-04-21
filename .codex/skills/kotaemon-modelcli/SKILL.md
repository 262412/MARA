---
name: kotaemon-modelcli
description: Use this skill for shared model routing workflows through `kotaemon modelcli ...`.
version: 1.0.0
---

# Kotaemon ModelCLI

## Scope

Use this skill for model routing workflows through the shared `kotaemon modelcli ...` CLI.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command Set

- `kotaemon modelcli init-config --output modelcli.yml`
- `kotaemon modelcli providers --config modelcli.yml`
- `kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml --dry-run`
- `kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml`

## Focused Action Skills

- `kotaemon-modelcli-init-config`
- `kotaemon-modelcli-providers`
- `kotaemon-modelcli-run`

Use this umbrella skill when the user needs more than one model routing action in one workflow.
