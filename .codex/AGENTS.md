# Slide Codex Agent Profile

Session discipline:

1. Validate environment and config before running model calls.
2. Prefer dry-run first for new model aliases or provider routes.
3. Record command, exit code, and remediation on errors.
4. Avoid destructive shell commands unless user explicitly requests.
5. Treat `slide ...` as the top-level slide/deck/workspace CLI line, including high-permission actions such as `slide write`, `slide delete`, and `slide shell`.
6. Treat `slide docqa ...` as the focused document-QA line; prefer focused `$slide-docqa-*` skills when the user asks for indexing, asking, chat, sessions, resume, files, delete, or doctor.
7. Use `$slide-app`, `$slide-model`, and `$slide-platform` for app runtime, model routing, and Codex/Claude Code support asset workflows.
8. Before non-trivial development, follow `docs/development/codebase-hygiene-contract.md`; `slide` CLI contract preservation is the top priority.
