---
name: kotaemon-docqa
description: This skill should be used when the user wants Kotaemon document QA, document indexing, or resumable document chat through the CLI while matching the app's QA flow.
version: 1.0.0
---

# Kotaemon DocQA

## Scope

Use this skill to drive Kotaemon document QA through `kotaemon docqa ...` commands.

## Core Workflow

1. Run `kotaemon docqa doctor` in a fresh environment.
2. Index missing documents with `kotaemon docqa index`.
3. Review the available collection with `kotaemon docqa files` if file scope matters.
4. Run `kotaemon docqa ask --prompt "..."` for a single QA turn.
5. Run `kotaemon docqa chat` or `kotaemon docqa resume <conversation-id>` for multi-turn work.

## Command Set

- `kotaemon docqa doctor`
- `kotaemon docqa index <path...> [--reindex]`
- `kotaemon docqa files`
- `kotaemon docqa delete <file-id-or-name>...`
- `kotaemon docqa ask --prompt "..."`
- `kotaemon docqa chat`
- `kotaemon docqa sessions`
- `kotaemon docqa resume <conversation-id>`
- `kotaemon docqa acceptance`

## Parameter Reference

Shared `ask` / `chat` options:

- `--conversation <conversation-id>`: continue an existing saved conversation.
- `--file <file-id-or-name>`: restrict retrieval to one or more indexed files. Repeat for multiple files.
- `--active-file <file-id-or-name>`: set the active file for page-focused QA when multiple files are selected.
- `--page <n>`: enable page-level QA for one page. If omitted, use whole-document QA.
- `--selected-text "..."`: focus retrieval on a text span without forcing page 1.
- `--graph-context-file <path.json>`: inject graph context from a JSON file.
- `--reasoning <reasoning-id>`: temporarily override the reasoning pipeline.
- `--llm <llm-name>`: temporarily override the chat model.
- `--citation highlight|inline|off`: override citation rendering.
- `--language <language>`: force the response language.
- `--mindmap`: request mindmap output when supported.
- `--json`: emit structured JSON output.

Other command options:

- `doctor --json`
- `index <path...> [--reindex] [--json]`
- `files [--json]`
- `delete <file-id-or-name>... [--json]`
- `sessions [--json]`
- `resume <conversation-id> [--json]`
- `acceptance [--keep-artifacts] [--verbose] [--json]`

## Scope Examples

- Whole-document QA: `kotaemon docqa ask --file report.pdf --prompt "Summarize this document"`
- Page-level QA: `kotaemon docqa ask --file report.pdf --active-file report.pdf --page 12 --prompt "What does this page say?"`
- Text-focused QA: `kotaemon docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"`

## Quality Gates

- `doctor` succeeds before running QA in a new workspace.
- Retrieval scope is explicit when the user names files.
- Answers include evidence output.
- Sessions remain resumable across CLI and app usage.
