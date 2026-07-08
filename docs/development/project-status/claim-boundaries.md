# Thesis Claim Boundaries

Last updated: 2026-07-07.

This document is the claim-boundary source for dissertation text,
proposal-facing reports, and demo narrative. Historical benchmark artifacts and
run reports keep their original provenance; any higher-level summary must apply
the boundaries below.

## Core Claim

MARA is a local-first, route-aware, multimodal document-QA research prototype
with a shared Web/CLI runtime, typed DocQA request/response contracts,
inspectable answer/evidence/citation/controller/verification artifacts, multiple
retrieval and reasoning route families, lightweight graph and multimodal route
engineering, study artifact generation, and a normalized framework for local
diagnostic evaluation.

## Completed System Artifacts

These can be described as implemented artifacts:

- Web/CLI shared DocQA runtime.
- `MARA`, `MARA-cli`, and `MARA docqa` public command surface.
- `DocQARequest` / `DocQAResponse` typed contract.
- Answer, citation/reference, evidence metadata, controller decision, route
  decision, retrieve decision, verify decision, guardrail decision, controller
  trace, and evidence bundle fields.
- Route and executor registry covering direct answer, text RAG, page-image VLM,
  element, hybrid, controller-auto, CRAG-style guarded, local graph, and abstain
  route families.
- Self-RAG-inspired controller semantics: route selection, retrieve, evidence
  evaluation, retry, route switch, verify, revise, and abstain.
- Benchmark harness: manifest v2, route matrix, benchmark prompt policy,
  `gold_answer_v1`, `/no_think`, score authority, timeout/failure/routing
  taxonomy, summary/report artifacts, offline rescoring.
- Multimodal route plumbing: VLM route health/readiness, visual retriever
  metadata, page-image records, OCR/layout element sidecar, persisted element
  index path, and request-level `element_index_records`.
- Local lightweight graph route, graph evidence, and graph context.
- Study artifact generation for study guide, quiz, flashcards, mindmap, slide
  outline, briefing doc, FAQ, timeline, custom report, data table, infographic,
  and slide deck.

Important wording limits:

- Write "Self-RAG-inspired controller semantics", not production-level Self-RAG
  reproduction.
- Write "local lightweight graph route", not full GraphRAG.
- Write audio/video overview as script/plan-first, not real `mp3/mp4` media
  export.

## Local Adapted Diagnostics

These metrics can explain system behavior and failure modes, but cannot be
written as official benchmark, leaderboard, or paper-grade external scores:

- Generic EM, F1, ANLS, answer token length, numeric match, formula match.
- Local dataset-native scores, including FinanceBench local answer correctness,
  QASPER local answer/evidence score, ALCE local correctness/citation score,
  RAGTruth local hallucination-span-style score, SlideVQA/MMDocRAG local visual
  QA score, and ViDoRe retrieval diagnostics.
- MARA diagnostic proxy score.
- Citation/evidence diagnostics: metadata citation recall/precision, inline
  citation recall/precision, gold page/source/span hit, page/doc/span hit,
  element/table/figure/formula/slide hit.
- Route/controller diagnostics: route-level native/proxy/F1, route ranking,
  route confusion, selected vs recommended route, question-type split, backend
  status by route, failure taxonomy, routing taxonomy.
- Guardrail/verifier diagnostics: abstention, false abstention, unsupported
  claim, rewrite skipped, guardrail expectation match, CRAG-style failure
  counts/classes.
- Runtime/performance diagnostics: parse/index/retrieval/generation seconds,
  total seconds, cache mode, executed/skipped routes.

Current benchmark-cycle note:

- The 2026-07-05 fullsystem postfix synthesis and 2026-07-07 RAGTruth repair
  freeze the final thesis claim boundary. The benchmark package is
  local-adapted only. The ALCE proxy evaluator proves plumbing but is not
  paper-grade.
- The final synthesis closes a local-adapted thesis evidence package, not an
  official leaderboard, external-evaluator, or global route-superiority
  package.
- SlideVQA is the primary local-adapted multimodal thesis dataset: job
  `9559018`, 25 examples, four-route multimodal matrix, and zero prediction
  errors.
- The `controller_auto` row must be discussed with the final controller
  route-decision summary. It supports inspectable controller routing, not a
  learned-router or global controller-superiority claim.
- MMDocRAG is secondary visual stability evidence: jobs `9559019` and
  `9559020` validate page-image and hybrid execution with GPU-ColVision / 8k
  VLM settings, with text baseline diagnostic job `9559021`, but do not
  establish matched full-route superiority.
- FinanceBench, QASPER, ALCE, and RAGTruth are supporting diagnostics unless
  promoted by larger matched reruns, not main headline thesis datasets.
- RAGTruth long-prompt execution failures are a completed prompt-policy repair
  claim: the original 11 execution errors were caused by Qwen 4k prompt-budget
  overflow from long `gold_answer_v1` source prompts, and the fix was validated
  on the five affected examples with direct and lexical local-Qwen reruns
  producing 5/5 `NO_ERROR` each. This supports a prompt-budget robustness
  claim, not a route-quality improvement claim.
- The original DocQA all-route RAGTruth repair manifest remains residual
  backend evidence because the 8002 retrieval endpoint rate-limited during the
  rerun. Do not describe that route matrix as fully repaired or quality
  validated.
- ViDoRe current rows are retrieval diagnostics only, not full answer-generation
  QA claims.
- Element RAG has nonzero but sparse MMDocRAG coverage evidence, so it may be
  described as a sparse-coverage failure. It must not be described as an
  Element RAG quality gain.
- Task 6 attribution and Task 7 guardrail reports are local diagnostics only:
  inline citation evidence is absent in current candidates, and guarded-route
  unsupported-claim detection is not calibrated paper-grade detection.
- Task 8 format evidence is diagnostic only: 6/7 complex synthetic samples
  indexed and 5/7 query turns found expected answers, but DOCX/CSV issues
  remain and preview/OCR were not exercised.

## Out Of Final Claim Or Future Work

These must not be written as completed current-system claims:

- Paper-grade external evaluator results and official leaderboard scores.
- Production-level Self-RAG, CRAG, GraphRAG, MMDocRAG reproduction.
- Trainable or learnable router.
- Full GraphRAG, including community detection, global query-focused
  summarization, and graph construction quality evaluation.
- Production ColPali / ColQwen benchmark claim.
- Broad stable large-sample VLM performance beyond the clean local-adapted
  SlideVQA/MMDocRAG evidence package.
- Original DocQA all-route RAGTruth repair quality claim until the 8002
  retrieval backend is stable and the route-matrix repair rerun completes.
- Element RAG stable answer-quality improvement on real non-gold OCR/layout
  corpus.
- Calibrated verifier thresholds and paper-grade attribution/hallucination
  evaluation.
- Full production-style format robustness, including preview, OCR, DOCX
  conversion, CSV retrieval, complex PPTX, Excel formulas, and charts.
- Rich graph UI with full-screen pan/zoom/filter/study-guide views.
- Real audio/video media export.
- Global claim that controller, hybrid, or guarded routes are stably superior
  to text RAG.

## Extension Classification

| Extension item                       | Classification             | Current state                                         | Thesis wording                                                         |
| ------------------------------------ | -------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------- |
| Trainable / learnable router         | Future work                | Current router is heuristic / structured planner path | Future work only                                                       |
| Full GraphRAG                        | Scoped extension           | Current graph route is local evidence/summary path    | Local lightweight graph route                                          |
| Rich graph interaction               | Scoped UI extension        | Current UI has knowledge graph, mindmap, source scope | Rich graph workbench is future work                                    |
| Real media artifact export           | Scoped media extension     | Audio/video overview is script/plan-first             | Media adapter required                                                 |
| Production-level system reproduction | Future work / out of claim | Current system is inspired/adapted                    | Do not claim full Self-RAG/CRAG/ColPali/GraphRAG/MMDocRAG reproduction |
