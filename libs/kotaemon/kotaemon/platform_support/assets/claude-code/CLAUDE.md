# Slide Claude Code Profile

This profile adds focused workflows for the user-facing MARA CLI.

If `MARA` is not installed yet, use `pip install slide-cli` or `uv tool install slide-cli`, then run `MARA doctor`.

Recommended checks:

1. MARA doctor
2. MARA app doctor
3. MARA model providers --config modelcli.yml
4. MARA model run --prompt "health check" --model ds-chat --provider openai --config modelcli.yml --dry-run
5. MARA docqa doctor

Preferred DocQA entry points:

1. Use `MARA-docqa-ask` for one-shot QA.
2. Use `MARA-docqa-index` to ingest documents.
3. Use `MARA-docqa-chat` and `MARA-docqa-resume` for multi-turn sessions.
4. Use `MARA-docqa-doctor` for health checks.
5. Use the umbrella `MARA-docqa` workflow when the task spans multiple DocQA actions.

Preferred model routing entry points:

1. Use `MARA-model-init-config` to generate a config.
2. Use `MARA-model-providers` to inspect provider availability.
3. Use `MARA-model-run` for one routed call, usually with `--dry-run` first.
4. Use the umbrella `MARA-model` workflow when the task spans multiple model routing actions.

Preferred packaged app entry points:

1. Use `MARA-app-init` to bootstrap user config.
2. Use `MARA-app-doctor` to inspect runtime health.
3. Use `MARA-app-run` to launch the packaged Web UI.
4. Use the umbrella `MARA-app` workflow when the task spans multiple app actions.

Preferred platform support entry points:

1. Use `MARA-platform-list` to inspect supported platforms.
2. Use `MARA-platform-install` to install Codex or Claude Code support assets.
3. Use `MARA-platform-status` to inspect installed assets.
4. Use `MARA-platform-validate` before publishing or after install.
5. Use the umbrella `MARA-platform` workflow when the task spans multiple platform actions.

Preferred slide entry points:

1. Use `MARA` for top-level slide/deck/workspace workflows.
2. Use focused `MARA-*` commands for narrow top-level actions such as `MARA-review`, `MARA-inspect`, `MARA-write`, `MARA-delete`, and `MARA-shell`.
3. Confirm intent before high-permission actions that mutate files or run shell commands.
4. Use `MARA-docqa` for MARA-owned document QA workflows.
5. Use focused `MARA-docqa-*` commands for narrow DocQA actions such as `MARA-docqa-index`, `MARA-docqa-ask`, and `MARA-docqa-chat`.

If a user already maintains CLAUDE.md, merge this profile manually from CLAUDE.slide.md.
