---
name: kotaemon-modelcli-run
description: Use this skill to run one routed completion through modelcli.
version: 1.0.0
---

# Kotaemon ModelCLI Run

## Scope

Use this skill to run one completion through the model router.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml --dry-run`
- `kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml`

## Relevant Parameters

- `--prompt "..."` (required)
- `--model <name>` (required)
- `--provider <name>`
- `--system-prompt "..."`
- `--temperature <float>`
- `--max-tokens <n>`
- `--config <path>`
- `--dry-run`

## Quality Gates

- Use `--dry-run` first for new routes.
- Real runs only happen after the route looks correct.
