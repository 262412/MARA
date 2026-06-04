---
name: MARA-docqa-ask
description: Use when the user wants one MARA-focused DocQA answer through `MARA docqa ask`.
version: 1.0.0
---

# MARA DocQA Ask

Use this skill for a single slide QA turn.

Recommended flow:

1. Validate the runtime with `MARA docqa doctor` if the environment is new.
2. Run `MARA docqa ask`.
3. Use `MARA docqa chat` or `MARA docqa resume` for follow-up questions.

Examples:

- `MARA docqa ask --file deck.pptx --prompt "Rewrite this slide for executives"`
- `MARA docqa ask --reasoning mara --task study_guide --artifact study_guide --prompt "Create a study guide"`
