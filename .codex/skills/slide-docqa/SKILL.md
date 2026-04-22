---
name: slide-docqa
description: Use when the user wants slide-focused document QA through `slide docqa ...` or the top-level aliases.
version: 1.0.0
---

# Slide DocQA

## Scope

Use this skill for slide-owned document QA, indexing, browsing, and resumable chat through the `slide docqa ...` command group.

If the user is working from the packaged runtime, prefer:

- `pip install "kotaemon-app[slide]"`
- `kotaemon app init`
- `kotaemon app doctor`
- `slide docqa --help`

## Core Workflow

1. Run `slide docqa doctor` in a fresh environment.
2. Index missing files with `slide docqa index`.
3. Review the collection with `slide docqa files` when file scope matters.
4. Run `slide docqa ask` or the `slide ask` alias for a single QA turn.
5. Use `slide docqa chat` or `slide docqa resume` for multi-turn work.

## Top-Level Shortcuts

- `slide ask`
- `slide index`
- `slide files`
- `slide docqa-sessions`
- `slide resume-docqa`

Use `slide resume` for the separate phase-1 slide-session workflow.

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `slide-docqa-ask`
- `slide-docqa-index`
- `slide-docqa-files`
- `slide-docqa-sessions`
- `slide-docqa-resume`
- `slide-docqa-chat`
- `slide-docqa-doctor`
