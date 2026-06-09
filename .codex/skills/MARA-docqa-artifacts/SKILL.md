---
name: MARA-docqa-artifacts
description: Use when the user wants generated MARA DocQA study artifacts through `MARA docqa artifacts ...`.
version: 1.0.0
---

# MARA DocQA Artifacts

Use this skill for generated study artifacts saved to a MARA DocQA conversation.

Common commands:

- `MARA docqa artifacts generate <conversation-id> --type study_guide`
- `MARA docqa artifacts generate <conversation-id> --type quiz --scope document`
- `MARA docqa artifacts list <conversation-id>`
- `MARA docqa artifacts show <conversation-id> --artifact <artifact-id>`
- `MARA docqa artifacts export <conversation-id> --artifact <artifact-id> --format md --output artifact.md`
- `MARA docqa artifacts evaluate <conversation-id> --artifact <artifact-id> --json`
- `MARA docqa artifacts evaluate <conversation-id> --json`
- `MARA docqa artifacts save-note <conversation-id> --artifact <artifact-id>`
- `MARA docqa artifacts regenerate <conversation-id> --artifact <artifact-id>`
- `MARA docqa artifacts delete <conversation-id> --artifact <artifact-id>`

Supported artifact types:

- `study_guide`, `quiz`, `flashcards`, `mindmap`, `slide_outline`
- `briefing_doc`, `faq`, `timeline`, `custom_report`, `data_table`
- `infographic`, `slide_deck`, `audio_overview`, `video_overview`

Export notes:

- `md`, `html`, `json`, `csv`, `svg`, and `pptx` are local exports.
- `mp3` and `mp4` require `KH_MARA_ARTIFACT_MEDIA_EXPORT_ADAPTER`.
- `evaluate` reports local `proxy_metric` values and does not claim paper-grade evaluation.
- Omit `--artifact` on `evaluate` to summarize all notebook artifacts and source
  formats.

Run `MARA docqa sessions` first if the conversation id is unknown.
