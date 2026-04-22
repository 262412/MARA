---
name: slide-docqa-index
description: Use when the user wants to ingest slide files through `slide index` or `slide docqa index`.
version: 1.0.0
---

# Slide DocQA Index

Use this skill when the task is to ingest slides or supporting documents into the slide DocQA runtime.

Recommended flow:

1. Run `slide docqa doctor` in a fresh environment.
2. Index files with `slide index` or `slide docqa index`.
3. Re-check the collection with `slide files` when you want to confirm what is available.

Examples:

- `slide index ./deck.pptx`
- `slide docqa index ./deck.pptx ./notes/`

