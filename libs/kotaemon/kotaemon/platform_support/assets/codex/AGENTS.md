# MARA Codex workflow

These instructions apply only to tasks that use the MARA product. For development
inside a MARA checkout, follow that checkout's AGENTS.md and its relevant gates.

- Use the focused `MARA-*` skill matching the requested command; use `$MARA`
  for workflows spanning command groups.
- `MARA ...` covers slide/deck/workspace actions; `MARA docqa ...` covers
  indexed-document QA and its saved conversations. Keep their data and sessions
  distinct.
- Check for the CLI only when the task needs to execute it. If missing, install
  `mara-research-cli` with `uv tool install mara-research-cli` or the appropriate
  existing environment, then run the doctor for the requested workflow.
- Validate effective environment and configuration before model calls. Reuse
  still-valid checks; inspect persisted settings when they override file values.
- Continue authorized actions through their requested output and focused checks.
  Ask for clarification only when the target or scope is unresolved. Preserve
  existing data and report the command, exit code, and remediation for errors.
