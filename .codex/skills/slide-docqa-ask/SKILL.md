---
name: slide-docqa-ask
description: Use when the user wants one slide-focused DocQA answer through `slide ask` or `slide docqa ask`.
version: 1.0.0
---

# Slide DocQA Ask

Use this skill for a single slide QA turn.

Recommended flow:

1. Validate the runtime with `slide docqa doctor` if the environment is new.
2. Run `slide ask` or `slide docqa ask`.
3. Use `slide docqa chat` or `slide docqa resume` for follow-up questions.

Examples:

- `slide ask --file deck.pptx --prompt "Summarize the opening"`
- `slide docqa ask --file deck.pptx --prompt "Rewrite this slide for executives"`

