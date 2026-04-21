---
name: kotaemon-cli-operations
description: This skill should be used when the user asks to validate, troubleshoot, or automate kotaemon CLI operations such as modelcli routing, promptui startup, and benchmark execution.
version: 1.0.0
---

# Kotaemon CLI Operations

## Scope

Use this skill to guide users through predictable kotaemon CLI workflows.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Core Workflow

1. Confirm working directory and virtual environment.
2. Run provider and config validation commands.
3. Execute dry-run before network calls.
4. Execute real call and summarize results.
5. Capture failures with exact command and remediation.

## Focused Skills

Prefer these focused skills when the user intent is narrow:

- `kotaemon-modelcli-init-config`
- `kotaemon-modelcli-providers`
- `kotaemon-modelcli-run`
- `kotaemon-app-init`
- `kotaemon-app-doctor`
- `kotaemon-app-run`

Keep this umbrella skill for promptui, benchmark, or mixed CLI workflows.

## Command Set

- `kotaemon modelcli init-config --output modelcli.yml`
- `kotaemon modelcli providers --config modelcli.yml`
- `kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml --dry-run`
- `kotaemon modelcli run --prompt "..." --model ds-chat --provider openai --config modelcli.yml`
- `kotaemon promptui run promptui.yml --port 7860`
- `python -m benchmark run --manifest benchmark/manifests/format_robustness.json --suite-name smoke`

## Quality Gates

- `providers` reports the expected provider as available.
- Dry-run resolves model and provider correctly.
- Real run returns model output without exception.
- Benchmark run exits with code 0 and produces artifacts.
