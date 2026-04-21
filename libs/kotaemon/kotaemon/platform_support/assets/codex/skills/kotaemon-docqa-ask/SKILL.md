---
name: kotaemon-docqa-ask
description: Use this skill to run one DocQA question through the shared CLI.
version: 1.0.0
---

# Kotaemon DocQA Ask

## Scope

Use this skill for one-shot document QA through `kotaemon docqa ask`.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa doctor`
- `kotaemon docqa ask --prompt "..."`

## Relevant Parameters

- `--file <file-id-or-name>` to restrict retrieval to one or more indexed files
- `--active-file <file-id-or-name>` for page-focused QA when multiple files are selected
- `--page <n>` for explicit page-level QA
- `--selected-text "..."` to focus on a specific snippet
- `--conversation <conversation-id>` to continue an existing conversation
- `--graph-context-file <path.json>`
- `--reasoning <reasoning-id>`
- `--llm <llm-name>`
- `--citation highlight|inline|off`
- `--language <language>`
- `--mindmap`
- `--json`

## Examples

- Whole-document QA: `kotaemon docqa ask --file report.pdf --prompt "Summarize this document"`
- Page-level QA: `kotaemon docqa ask --file report.pdf --page 12 --prompt "What does this page say?"`
- Text-focused QA: `kotaemon docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"`

## Quality Gates

- `doctor` succeeds before the first QA call in a fresh environment.
- File scope is explicit when the user names files.
- Answers include evidence output.
