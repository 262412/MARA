---
name: MARA-write
description: "Create or update workspace files through MARA write."
version: 1.0.0
---

# MARA Write

## Scope

Use this skill when the user wants to create new files or update existing files through `MARA write`.

## Command

- `MARA write`

## Focus

Resolve the target path and content from the request and existing context, then perform the authorized write. Ask only when either is ambiguous or overwriting unrelated data would require new authorization.
