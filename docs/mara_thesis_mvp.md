# MARA Thesis MVP

This document records the product and research contract for the MARA thesis
prototype. It is intentionally scoped to the v1 thesis MVP rather than a full
NotebookLM clone.

## Research Claim

MARA is an agentic multimodal document QA framework built on the existing
Kotaemon/Slides runtime. The thesis claim is:

> Agentic multimodal retrieval and verification improves grounding, evidence
> selection, and reliability compared with fixed RAG pipelines for documents,
> images, tables, formulas, and presentation slides.

## Capability Matrix

| Capability                 | NotebookLM Reference                   | MARA v1 Target                                        | Current MARA Surface                                           |
| -------------------------- | -------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------- |
| Source upload and indexing | Broad document and web sources         | Local document/source indexing                        | Web UI file index and `MARA docqa index`                       |
| Grounded chat              | Source-grounded answers with citations | Citation-backed DocQA and page-aware QA               | Web UI chat, `MARA docqa ask/chat`                             |
| Source selection           | Notebook source include/exclude        | Persisted selected source ids per conversation        | `MARA docqa sources select/list` and graph source state        |
| Source guide               | Per-source summaries and prompts       | Per-source summary, key topics, suggested questions   | `MARA docqa sources guide`                                     |
| Notes                      | Manual and generated notes             | Manual notes, answer notes, note-to-source conversion | `MARA docqa notes add/save-answer/convert-source`              |
| Mind map                   | Source-grounded mind map               | Existing knowledge graph/mindmap with source scope    | Web UI Knowledge Map and graph-source persistence              |
| Study guide                | Generated study guide                  | Source-grounded structured artifact                   | MARA reasoning artifact and `MARA docqa artifacts`             |
| Quiz and flashcards        | Generated study aids                   | Source-backed quiz/flashcard artifacts                | MARA artifact request fields and saved artifacts               |
| Slide artifact             | Generated slide deck                   | Slide outline first; export is stretch                | `slide_outline` artifact type, PDF/PPTX export remains stretch |
| Agent trace                | Not a core end-user feature            | Required thesis transparency signal                   | Response `agent_trace`, Web UI trace card, benchmark rows      |
| Audio/video/infographic    | Product feature                        | Out of v1 scope                                       | Not implemented                                                |
| Public sharing/sync/mobile | Product feature                        | Out of v1 scope                                       | Not implemented                                                |

## Research Questions

1. Does MARA improve answer grounding over direct paste and fixed RAG baselines?
2. Does modality-aware routing improve table, figure, formula, and slide QA?
3. Does claim verification reduce unsupported answers without excessive false
   abstention?
4. Does the agent trace provide enough evidence for failure analysis in a thesis
   evaluation?

## MVP Scope

Must-have:

- MARA reasoning mode with fast and thorough agent modes.
- Citation-backed DocQA responses with agent trace and evidence metadata.
- Source selection, source guide, notes, and note-to-source workflows.
- Study artifacts: study guide, quiz, flashcards, mind map, and slide outline.
- Benchmark routes for direct paste, oracle page, DocQA, and MARA ablations.

Should-have:

- UI presentation for citations, trace, source scope, and knowledge map.
- Slide outline export path if the core agent and evaluation are stable.

Out of scope for v1:

- Full audio/video generation.
- Public sharing, Google Drive sync, and mobile apps.
- Infographic image generation.

## Benchmark Baselines

Use the normalized benchmark manifest v2 route matrix in
`benchmark/README.md`.

Required routes:

- `direct_paste_document`
- `oracle_page`
- `docqa_document`
- `docqa_page`
- `docqa_multi_document`
- `mara_fast`
- `mara_thorough`

Required reporting fields:

- Answer quality: EM, F1, ANLS, numeric tolerance, formula match.
- Grounding: page hit, citation recall, element hit, span recall.
- Multimodal: table hit, figure hit, formula hit, slide hit.
- Reliability: abstention rate, false abstention, claim verification rewrite
  status.
- Efficiency: parse/index/retrieval/generation timings and cache statistics.
- Traceability: `agent_trace`, `evidence_metadata`, `claim_verification`, and
  retrieval traces.

## Demo Script

1. Start the runtime:

   ```powershell
   MARA app doctor
   MARA app run
   ```

2. Index one PDF, one PPTX, one table-heavy file, and one image/figure-heavy
   source:

   ```powershell
   MARA docqa index docs/demo/paper.pdf docs/demo/slides.pptx docs/demo/table.xlsx
   ```

3. Select the thesis demo sources for a conversation:

   ```powershell
   MARA docqa sources select <conversation-id> --file paper.pdf --file slides.pptx
   MARA docqa sources guide <conversation-id>
   ```

4. Ask a grounded MARA question:

   ```powershell
   MARA docqa ask --prompt "What evidence supports the main claim?" --reasoning mara --agent-mode thorough
   ```

5. Ask one modality-specific question for a table, figure, formula, or slide.
   Confirm the response includes citations, evidence metadata, and an agent
   trace.

6. Save a useful answer as a note and convert the note into a source:

   ```powershell
   MARA docqa notes save-answer <conversation-id> --title "Grounding note"
   MARA docqa notes convert-source <conversation-id> --note <note-id>
   ```

7. Generate at least two study artifacts:

   ```powershell
   MARA docqa artifacts generate <conversation-id> --type study_guide
   MARA docqa artifacts generate <conversation-id> --type quiz
   MARA docqa artifacts list <conversation-id>
   ```

8. Run a small benchmark route matrix and inspect `report.md`,
   `predictions.jsonl`, and `retrieval_traces.jsonl`:

   ```powershell
   python -m benchmark run --manifest benchmark/manifests/mara_demo.json --suite-name mara-demo --route all
   ```

## Acceptance Checklist

- Public CLI help shows `MARA` commands, not user-facing `slide` commands.
- `MARA docqa ask --reasoning mara` returns an answer, trace, evidence metadata,
  and saved artifact payload when an artifact is requested.
- Source selection persists in the conversation notebook state.
- Notes and generated artifacts survive session reload through conversation
  `data_source`.
- Benchmark outputs include MARA trace fields and multimodal hit summaries.
- Hygiene ratchet and changed-file pre-commit gates pass without updating
  `scripts/codebase_hygiene_baseline.json`.

## Residual Risks

- The Chat Page remains a high-risk UI module because construction, event
  binding, preview, DocQA state, and graph behavior are still concentrated in
  `libs/ktem/ktem/pages/chat/__init__.py`.
- The Web UI has citation and reasoning trace surfaces, but richer notebook
  panels for notes and artifacts should be added behind explicit Gradio
  contract tests.
- Full PPTX/PDF slide deck generation is still stretch scope; the stable v1
  artifact is the grounded slide outline.
