---
name: MARA-docqa
description: Use when the user wants MARA-focused document QA through `MARA docqa ...`.
version: 1.0.0
---

# MARA DocQA

## Scope

Use this skill for MARA-owned document QA, indexing, browsing, deleting, source selection, notes, generated artifacts, session management, and resumable chat through the `MARA docqa ...` command group.

## Core Workflow

1. Run `MARA docqa doctor` in a fresh environment.
2. Index missing files with `MARA docqa index`.
3. Review the collection with `MARA docqa files` when file scope matters.
4. Remove stale indexed files with `MARA docqa delete` when the collection is outdated.
5. Run `MARA docqa ask` for a single QA turn.
6. Use `MARA docqa chat` or `MARA docqa resume` for multi-turn work.
7. Use `MARA docqa sessions` to list saved conversations.
8. Use `MARA docqa sources` and `MARA docqa notes` for notebook-style source organization.
9. Use `MARA docqa artifacts` to inspect generated study artifacts saved to a conversation.

`MARA docqa acceptance` and `MARA docqa check` are still available, but treat them as maintainer workflows rather than part of the focused slide skill family.

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `MARA-docqa-ask`
- `MARA-docqa-index`
- `MARA-docqa-files`
- `MARA-docqa-delete`
- `MARA-docqa-sessions`
- `MARA-docqa-notes`
- `MARA-docqa-sources`
- `MARA-docqa-artifacts`
- `MARA-docqa-resume`
- `MARA-docqa-chat`
- `MARA-docqa-doctor`
