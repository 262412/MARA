# MARA Codex Agent Profile

Mandatory development contract: for every non-trivial repository change, follow
`docs/development/codebase-hygiene-contract.md`. Preserve the `MARA` /
`MARA-cli` public command surface, identify affected public surfaces before
editing, run the relevant verification gates, and do not refresh
`scripts/codebase_hygiene_baseline.json` just to make the hygiene gate pass.

Session discipline: 0. If `MARA` is missing, install the product CLI with `pip install mara-research-cli` or `uv tool install mara-research-cli`, then run `MARA doctor`.

1. Validate environment and config before running model calls.
2. Prefer focused MARA model skills when the user intent is specific:
   - `$MARA-model-init-config`
   - `$MARA-model-providers`
   - `$MARA-model-run`
3. Use `$MARA-model` or `MARA model ...` for shared routing workflows.
4. Prefer focused app skills when the user intent is specific:
   - `$MARA-app-init`
   - `$MARA-app-doctor`
   - `$MARA-app-run`
5. Use `$MARA-app` or `MARA app ...` when the user needs setup, inspection, and launch in one workflow.
6. Prefer focused DocQA skills when the user intent is specific:
   - `$MARA-docqa-ask` for one-shot QA
   - `$MARA-docqa-index` for ingest
   - `$MARA-docqa-chat` / `$MARA-docqa-resume` for multi-turn work
   - `$MARA-docqa-doctor` for health checks
7. Use `$MARA-platform` or focused `$MARA-platform-*` skills for Codex and Claude Code support asset workflows.
8. Treat `MARA ...` and `MARA docqa ...` as separate workflow lines:
   - Use `$MARA` or focused `$MARA-*` skills for top-level slide/deck/workspace actions, including high-permission commands such as `MARA write`, `MARA delete`, and `MARA shell`.
   - Use `$MARA-docqa` or focused `$MARA-docqa-*` skills for MARA-owned document QA only.
9. Record command, exit code, and remediation on errors.
10. Avoid destructive shell commands unless user explicitly requests.
