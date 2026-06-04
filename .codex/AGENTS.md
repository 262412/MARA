# Slide Codex Agent Profile

Session discipline:

1. Validate environment and config before running model calls.
2. Prefer dry-run first for new model aliases or provider routes.
3. Record command, exit code, and remediation on errors.
4. Avoid destructive shell commands unless user explicitly requests.
5. Treat `MARA ...` as the top-level slide/deck/workspace CLI line, including high-permission actions such as `MARA write`, `MARA delete`, and `MARA shell`.
6. Treat `MARA docqa ...` as the focused document-QA line; prefer focused `$MARA-docqa-*` skills when the user asks for indexing, asking, chat, sessions, resume, files, delete, or doctor.
7. Use `$MARA-app`, `$MARA-model`, and `$MARA-platform` for app runtime, model routing, and Codex/Claude Code support asset workflows.
8. Before non-trivial development, follow `docs/development/codebase-hygiene-contract.md`; `MARA` CLI contract preservation is the top priority.
