---
name: kotaemon-docqa-index
description: Use this skill to ingest files or URLs into the shared DocQA collection.
version: 1.0.0
---

# Kotaemon DocQA Index

## Scope

Use this skill to import local files or URLs into the default DocQA file collection.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa doctor`
- `kotaemon docqa index <path...> [--reindex]`

## Relevant Parameters

- `<path...>` supports one or more local paths or URLs
- `--reindex` replaces an existing indexed copy
- `--json` emits structured output

## Examples

- `kotaemon docqa index ./docs/report.pdf`
- `kotaemon docqa index ./docs/report.pdf ./docs/appendix.docx --reindex`

## Quality Gates

- `doctor` succeeds before ingestion in a fresh environment.
- Indexing reports zero failures.
