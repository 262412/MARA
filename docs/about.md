# About MARA

MARA is a local-first document research workbench for grounded question
answering, citation review, page preview, knowledge graph exploration, and
study artifact generation.

The application is designed around one shared runtime. The Web UI and
`MARA docqa` CLI use the same local file index, conversation store, source
selection, graph cache, and model configuration, so work started in the browser
can be inspected or automated from the terminal.

MARA is a branded fork of [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon),
distributed under the Apache License 2.0. Internal package names such as
`kotaemon`, `ktem`, and `slide_cli` remain for compatibility, while the public
product surface is `MARA` and `MARA-cli`.

Core workflows:

- Upload and index local documents such as PDF, Office files, images, Markdown,
  text files, spreadsheets, HTML/MHTML, CSV, and ZIP archives.
- Ask document-level, page-level, multi-document, or selected-text-focused
  questions.
- Review generated answers against citations, retrieved evidence, and document
  previews.
- Build a knowledge graph or Mind Map from selected sources and use graph nodes
  to drive follow-up questions.
- Generate source-grounded study artifacts such as study guides, quizzes,
  flashcards, mind maps, slide outlines, briefing documents, timelines, and
  custom reports.
- Use the `MARA` and `MARA docqa` command lines for repeatable indexing,
  question answering, sessions, notes, artifacts, model routing, and app
  lifecycle checks.

[Project README](../README.md) |
[CLI Release Notes](mara_research_cli_release.md) |
[Thesis MVP Scope](mara_thesis_mvp.md) |
[Upstream Source](https://github.com/Cinnamon/kotaemon)
