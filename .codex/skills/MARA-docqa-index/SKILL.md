---
name: MARA-docqa-index
description: Use when the user wants to ingest MARA files through `MARA docqa index`.
version: 1.0.0
---

# MARA DocQA Index

Use this skill when the task is to ingest slides or supporting documents into the MARA DocQA runtime.

Recommended flow:

1. Run `MARA docqa doctor` in a fresh environment.
2. Index files with `MARA docqa index`.
3. Re-check the collection with `MARA docqa files` when you want to confirm what is available.

Examples:

- `MARA docqa index ./deck.pptx ./notes/`
