# Slide Codex Agent Profile

Session discipline: 0. If `slide` is missing, install the product CLI with `pip install slide-cli` or `uv tool install slide-cli`, then run `slide doctor`.

1. Validate environment and config before running model calls.
2. Prefer focused slide model skills when the user intent is specific:
   - `$slide-model-init-config`
   - `$slide-model-providers`
   - `$slide-model-run`
3. Use `$slide-model` or `slide model ...` for shared routing workflows.
4. Prefer focused app skills when the user intent is specific:
   - `$slide-app-init`
   - `$slide-app-doctor`
   - `$slide-app-run`
5. Use `$slide-app` or `slide app ...` when the user needs setup, inspection, and launch in one workflow.
6. Prefer focused DocQA skills when the user intent is specific:
   - `$slide-docqa-ask` for one-shot QA
   - `$slide-docqa-index` for ingest
   - `$slide-docqa-chat` / `$slide-docqa-resume` for multi-turn work
   - `$slide-docqa-doctor` for health checks
7. Use `$slide-platform` or focused `$slide-platform-*` skills for Codex and Claude Code support asset workflows.
8. Treat `slide ...` and `slide docqa ...` as separate workflow lines:
   - Use `$slide` or focused `$slide-*` skills for top-level slide/deck/workspace actions, including high-permission commands such as `slide write`, `slide delete`, and `slide shell`.
   - Use `$slide-docqa` or focused `$slide-docqa-*` skills for slide-owned document QA only.
9. Record command, exit code, and remediation on errors.
10. Avoid destructive shell commands unless user explicitly requests.
