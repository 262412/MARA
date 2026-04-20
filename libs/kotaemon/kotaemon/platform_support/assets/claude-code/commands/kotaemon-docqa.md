---
description: Run Kotaemon document QA through the shared docqa CLI
argument-hint: [question]
allowed-tools: Bash(kotaemon:*)
---

Run a quick Kotaemon document QA workflow.

1. Validate the runtime first:
   !`kotaemon docqa doctor`

2. Run the question through the shared DocQA pipeline:
   !`kotaemon docqa ask --prompt "$ARGUMENTS"`

3. If the user asks for an interactive or resumable session, use:
   !`kotaemon docqa chat`

If the collection is empty, index files first with `kotaemon docqa index ...`.
