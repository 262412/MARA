---
description: Run the top-level MARA CLI workflow
argument-hint: [task]
allowed-tools: Bash(MARA:*)
---

Run a MARA workflow through the top-level CLI.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Use this umbrella command when the task spans multiple top-level MARA actions.
3. Prefer focused command wrappers when the user intent is specific:
   - `MARA-doctor`
   - `MARA-inspect`
   - `MARA-review`
   - `MARA-run`
   - `MARA-apply`
   - `MARA-export-pdf`
   - `MARA-chat`
   - `MARA-sessions`
   - `MARA-resume`
   - `MARA-files`
   - `MARA-read`
   - `MARA-read-slide`
   - `MARA-extract`
   - `MARA-search`
   - `MARA-write`
   - `MARA-delete`
   - `MARA-shell`
4. Use `MARA-docqa` and its focused wrappers for document QA work.
