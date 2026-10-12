---
name: MARA
description: "Coordinate MARA CLI tasks spanning multiple command groups."
version: 1.0.0
---

# MARA

Coordinate the top-level MARA CLI workflow across command groups.

Use the focused skill for a single action. For a mixed workflow, load only the
groups needed for the request:

- Slide/deck inspection, review, rewriting, patches, and PDF export: the matching
  `MARA-inspect`, `MARA-review`, `MARA-run`, `MARA-apply`, or `MARA-export-pdf` skill.
- Indexed-document QA, ingestion, notebooks, and conversations: `$MARA-docqa`.
- Packaged Web UI setup or launch: `$MARA-app`.
- Shared model routing: `$MARA-model`.
- Coding-platform support assets: `$MARA-platform`.
- Workspace files, shell commands, or saved slide sessions: the matching
  focused `MARA-*` skill.

Use `MARA --help` for the command inventory. If execution is required and the
CLI is missing, install `mara-research-cli` in the appropriate environment.
Validate environment and effective configuration before model calls.
Finish with the requested artifacts or answer and the relevant verification.

| Command           | Focused skill     |
| ----------------- | ----------------- |
| `MARA doctor`     | `MARA-doctor`     |
| `MARA inspect`    | `MARA-inspect`    |
| `MARA read-slide` | `MARA-read-slide` |
| `MARA extract`    | `MARA-extract`    |
| `MARA search`     | `MARA-search`     |
| `MARA review`     | `MARA-review`     |
| `MARA run`        | `MARA-run`        |
| `MARA apply`      | `MARA-apply`      |
| `MARA export-pdf` | `MARA-export-pdf` |
| `MARA chat`       | `MARA-chat`       |
| `MARA sessions`   | `MARA-sessions`   |
| `MARA resume`     | `MARA-resume`     |
| `MARA files`      | `MARA-files`      |
| `MARA read`       | `MARA-read`       |
| `MARA write`      | `MARA-write`      |
| `MARA delete`     | `MARA-delete`     |
| `MARA shell`      | `MARA-shell`      |
| `MARA docqa`      | `MARA-docqa`      |
| `MARA app`        | `MARA-app`        |
| `MARA model`      | `MARA-model`      |
| `MARA platform`   | `MARA-platform`   |
