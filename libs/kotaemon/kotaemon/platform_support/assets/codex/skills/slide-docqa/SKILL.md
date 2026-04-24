---
name: slide-docqa
description: Use when the user wants slide-focused document QA through `slide docqa ...`.
version: 1.0.0
---

# Slide DocQA

## Scope

Use this skill for slide-owned document QA, indexing, browsing, deleting, session management, and resumable chat through the `slide docqa ...` command group.

## Core Workflow

1. Run `slide docqa doctor` in a fresh environment.
2. Index missing files with `slide docqa index`.
3. Review the collection with `slide docqa files` when file scope matters.
4. Remove stale indexed files with `slide docqa delete` when the collection is outdated.
5. Run `slide docqa ask` for a single QA turn.
6. Use `slide docqa chat` or `slide docqa resume` for multi-turn work.
7. Use `slide docqa sessions` to list saved conversations.

`slide docqa acceptance` and `slide docqa check` are still available, but treat them as maintainer workflows rather than part of the focused slide skill family.

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `slide-docqa-ask`
- `slide-docqa-index`
- `slide-docqa-files`
- `slide-docqa-delete`
- `slide-docqa-sessions`
- `slide-docqa-resume`
- `slide-docqa-chat`
- `slide-docqa-doctor`
