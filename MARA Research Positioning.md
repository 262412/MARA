# MARA Research Positioning

## Week 1 conclusion

This document records the Week 1 research positioning for MARA. The goal of
this phase is to freeze feature expansion, identify the thesis-level problem,
and align the current codebase with a coherent research line.

The two source readings used for this positioning are:

- `C:\Users\22826\Downloads\deep-research-report (1).md`
- `C:\Users\22826\Downloads\MARA\2510.15253v3.pdf`

The A1 paper is *Scaling Beyond Context: A Survey of Multimodal
Retrieval-Augmented Generation for Document Understanding*. It frames document
RAG as a multimodal document understanding problem, not a simple text chunking
problem. Its central message is that OCR-only pipelines lose structure, native
multimodal LLMs struggle with very long document context, and robust document
understanding needs retrieval across text, page images, tables, charts, layout,
graphs, and agentic workflows.

## The three sentences

**First, MARA solves the problem of trustworthy question answering and
knowledge exploration over local, private, multi-format document collections.**
It is not just a PDF chat interface. The real problem is that users need to ask
questions across PDFs, Office files, slides, tables, notes, figures, formulas,
and long reports while still being able to inspect the exact page, source,
element, and evidence that supports each answer.

**Second, existing research has not fully solved this because most systems solve
only one part of the document intelligence stack.** Text-only RAG loses visual
layout and element-level evidence; long-context multimodal LLMs cannot reliably
scale to large document collections; visual retrievers improve page recall but
often stop before claim-level verification; GraphRAG helps global exploration
but is often weak on page-level grounding; agentic RAG improves routing and
reflection but adds coordination cost and still needs faithful evidence
evaluation.

**Third, MARA should solve this through a local-first agentic multimodal DocRAG
mechanism: hybrid document indexing, modality-aware retrieval, dynamic
fast/thorough routing, claim-level evidence verification, global/local graph
exploration, and a unified benchmark protocol.** The research contribution is
not adding more UI features, but proving whether this integrated mechanism
improves grounding, evidence selection, reliability, and error analysis over
fixed RAG and direct-paste baselines.

## Research problem

MARA should be positioned as:

> A local-first agentic multimodal DocRAG platform for trustworthy question
> answering and knowledge exploration over private document collections.

This is stronger than "a local RAG application" because it names the real
research object:

- local-first deployment for private documents;
- multimodal document evidence, including text, tables, figures, formulas,
  slides, page images, and layout;
- page-level and element-level grounding;
- agentic routing between fast, thorough, page, document, multi-document, and
  graph-oriented workflows;
- claim-level verification and abstention when evidence is insufficient;
- benchmarkable behavior rather than demonstration-only behavior.

The current project documents already support this direction. `docs/mara_thesis_mvp.md`
states that MARA's thesis claim is that agentic multimodal retrieval and
verification improves grounding, evidence selection, and reliability compared
with fixed RAG pipelines. `docs/proposal_draft.md` frames the product as a
research workbench with file index, chat, preview, citations, and knowledge
graph exploration. The deep research report reaches the same conclusion:
MARA's strongest path is not more feature expansion, but integrating retrieval,
routing, verification, graph exploration, and benchmark evaluation into one
research system.

## Why existing research is incomplete

The A1 survey gives the clearest reason to avoid a narrow text-RAG framing.
Document understanding is multimodal: real documents combine text, tables,
charts, images, formulas, layout, and cross-page structure. The survey organizes
the field by domain, retrieval modality, retrieval granularity, graph-based
enhancement, agent-based enhancement, datasets, benchmarks, applications, and
open challenges. That taxonomy maps directly onto MARA's codebase.

The research gap relevant to MARA is the integration gap:

| Prior direction | What it helps with | What remains incomplete for MARA's target |
| --- | --- | --- |
| Text-only RAG | Simple passage retrieval and grounded generation | Loses tables, charts, formulas, layout, page images, and visual evidence |
| Long-context MLLMs | Directly reading larger contexts | Context limits, cost, hallucination, and weak evidence localization remain |
| Visual/page retrievers | Better retrieval for visually rich pages | Often weak on answer verification, source workflow, graph exploration, and local deployment |
| GraphRAG | Global themes, entity relations, query-focused summarization | Often text-heavy and not always aligned with page/element-level evidence |
| Agentic RAG | Dynamic routing, query decomposition, reflection, retry | Coordination overhead and lack of unified faithfulness/cost evaluation |
| Citation systems | Surface-level source attribution | Citation is not the same as claim support |

Therefore the thesis gap is not "RAG does not exist." The gap is that document
RAG systems still struggle to combine multimodal evidence retrieval, adaptive
workflow control, local/private deployment, graph-level exploration, and
claim-level reliability evaluation in one reproducible system.

## MARA mechanism

MARA should be described as a system mechanism with six connected layers.

1. **Document ingestion and indexing**

   MARA ingests local documents, extracts text and metadata, stores file records,
   creates document chunks, and builds retrieval indexes. This is the system
   foundation for private document collections.

2. **Multimodal evidence representation**

   The system should preserve and expose text, table, figure, formula, slide,
   page, and element metadata. This is where MARA aligns with the A1 paper's
   emphasis on retrieval modality and granularity.

3. **Modality-aware retrieval and reranking**

   A query should not always follow the same text-vector route. MARA should
   identify whether the user is asking for text, table, figure, formula, slide,
   mixed, page-scoped, document-scoped, or multi-document evidence, then route
   and rerank accordingly.

4. **Agentic planning and control**

   MARA's `fast` and `thorough` modes should become a thesis-level agentic
   mechanism. Fast mode should optimize latency for simple grounded questions.
   Thorough mode should support retry, evidence sufficiency checks, verification,
   and abstention when the system cannot retrieve enough support.

5. **Claim-level verification**

   MARA should treat answer reliability as a first-class system output. The key
   question is not only whether an answer contains citations, but whether each
   factual claim is supported by retrieved page, span, element, or modality
   evidence.

6. **Global/local graph exploration**

   MARA's knowledge graph and mind map should not remain only a UI display. The
   research mechanism should connect local evidence retrieval with global graph
   exploration so users can move between page-level answers and corpus-level
   themes.

## Current code module map

The current repository already contains the main surfaces needed for this
research line. The Week 1 development task is to map and freeze these surfaces,
not to add unrelated functionality.

| Area | Current code surface | Research role |
| --- | --- | --- |
| UI | `libs/ktem/ktem/pages/chat/__init__.py`, `chat_panel.py`, `page_preview.py`, `studio_artifacts.py`, file index UI modules | Workbench interface for chat, source selection, citations, preview, graph, and artifacts |
| Runtime | `libs/ktem/ktem/docqa/runtime.py`, `_runtime_models.py`, `_runtime_mara.py`; `libs/slide_cli/slide_cli/docqa_cli.py` | Shared Web/CLI DocQA execution surface and persisted request/response state |
| Index | `libs/ktem/ktem/index/file/index.py`, `pipelines.py`; `libs/kotaemon/kotaemon/indices/vectorindex.py`, `elements.py`, `formulas.py` | File records, source/index tables, chunking, vector indexing, element metadata |
| Retriever | `DocumentRetrievalPipeline`, `VectorRetrieval`, `retrieval_quality.py`, local and LLM rerankers, `multimodal.py` | Evidence retrieval, reranking, query modality routing, optional multimodal plugin decisions |
| Agent | `libs/ktem/ktem/reasoning/mara.py`, plus `simple.py`, `react.py`, `rewoo.py` | MARA query understanding, modality planning, fast/thorough route, retry, trace, abstention |
| Graph | `knowledge_graph_service.py`, `knowledge_graph_builder.py`, `knowledge_graph_renderer.py`, `ktem/docqa/knowledge_graph.py`, `index/file/graph/*` | Conversation graph, mind map rendering, graph-source state, GraphRAG-style retrieval options |
| Benchmark | `benchmark/README.md`, `schemas.py`, `manifest.py`, `runner.py`, `engines.py`, `metrics.py`, `evidence_metadata.py` | Route matrix, direct-paste/oracle/DocQA/MARA ablations, grounding and modality metrics |

This map shows that the project already has enough structure for a research
prototype. The risk is not lack of features. The risk is unclear boundaries:
the chat page is still large, UI and runtime behavior are coupled, and Web/CLI
DocQA behavior can drift if the shared runtime is not treated as the single
source of truth.

## Research questions for Week 1 freeze

The Week 1 positioning should reduce the project to four research questions:

1. Does MARA improve answer grounding over direct paste and fixed RAG baselines?
2. Does modality-aware routing improve table, figure, formula, slide, and
   multi-page QA?
3. Does claim-level verification reduce unsupported answers without excessive
   false abstention?
4. Does the agent trace explain retrieval, verification, and failure decisions
   well enough for reproducible error analysis?

These match the current benchmark design in `benchmark/README.md`, which already
tracks answer quality, page hit, citation recall, element hit, table/figure/
formula/slide hit, abstention, claim verification behavior, evidence metadata,
latency, and traceability.

## What should be frozen now

For this phase, MARA should stop expanding its feature list. The frozen research
surface should be:

- `MARA` and `MARA-cli` command compatibility;
- Web UI file index, chat, citation, preview, and knowledge graph surfaces;
- shared DocQA runtime request and response fields;
- MARA reasoning mode with `fast` and `thorough` agent modes;
- source selection, page/document/multi-document scope, and graph source state;
- benchmark route matrix and evaluation fields.

New work should be accepted only if it strengthens the research mechanism or
the benchmark evidence. UI polish, new artifact types, extra model providers,
or broad product features should wait until the thesis mechanism is stable.

## Final positioning

MARA should be written as a research system, not as a feature collection:

> MARA is a local-first agentic multimodal DocRAG system that helps users ask
> trustworthy questions over private document collections by combining
> multimodal evidence retrieval, adaptive routing, claim-level verification,
> and global/local knowledge graph exploration.

The expected contribution is:

> MARA evaluates whether integrating modality-aware retrieval, agentic workflow
> control, and evidence verification in a local document workbench improves
> grounding, evidence selection, reliability, and failure analysis compared
> with fixed RAG and long-context direct-paste baselines.

This is the research line to protect during the next stages.
