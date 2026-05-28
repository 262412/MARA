# MARA: A Local Retrieval-Augmented Document QA and Knowledge Exploration System

Name: [Chenghao Zhang]
Student ID: [201844864]

## Statement of Ethical Compliance

Proposed data and participant categories: A0/A1 for public, synthetic or self-provided project documents, and C2 for a small adult usability evaluation with classmates or staff. I will follow the School ethical guidance, collect only necessary data, anonymise feedback, and confirm any change in participant activity or data type with my supervisor before it begins.

## Project Description

MARA will be a local document question-answering system that helps users search, understand and navigate their own documents through a web interface and command-line workflow. The project builds on the existing Python repository, a fork of Kotaemon/Slides, and focuses on retrieval-augmented generation (RAG), page-level document preview, citation review and knowledge graph exploration. A user will be able to upload documents such as PDFs, Word files, slides, spreadsheets, Markdown and text files, index them locally, then ask natural-language questions. The system will retrieve relevant passages, generate an answer, show the source evidence, and allow the user to inspect the original page or document section.

Ordinary file search is weak for complex academic or professional documents, while generic chatbots may answer without showing where their claims came from. MARA will therefore combine conversational interaction with visible evidence. The final application should look like a research workbench: a file index, a chat area, a document preview panel, and a knowledge graph viewer for exploring relationships between topics.

## Aims and Requirements

The aims of the project are:

- To develop a usable local RAG application for document question answering with clear citation and preview support.
- To improve transparency by linking generated answers to retrieved evidence, page previews and a conversation knowledge graph.
- To evaluate whether the system meets practical user needs for searching, summarising and exploring multi-format documents.

Essential requirements:

- Users can upload and index supported document formats, including PDF, Office, text and Markdown files.
- Users can ask questions over all indexed documents or selected files.
- The system retrieves relevant document chunks and generates answers with citations.
- Users can open cited sources in a preview panel and inspect page-level evidence.
- Conversations and indexes are persisted locally so the web UI and CLI can share the same runtime state.
- The application includes a knowledge graph or mind-map style view that helps users explore document topics and ask follow-up questions.
- The project includes automated tests for indexing, retrieval, citation handling, CLI behaviour and important UI services.

Desirable requirements:

- Local-model support for privacy-sensitive use cases.
- A fullscreen knowledge graph viewer with pan and zoom.
- A small benchmark set for comparing retrieval quality across example questions.
- A polished light and dark UI theme suitable for long reading sessions.

## Key Literature and Background Reading

The technical basis of the project is retrieval-augmented generation. Lewis et al. describe RAG as a method that combines a parametric language model with a non-parametric external knowledge source, allowing generated answers to be grounded in retrieved passages rather than relying only on model memory [1]. This directly supports MARA's design: documents are first indexed, then retrieved evidence is supplied to the answer-generation pipeline.

Dense retrieval is also important. Karpukhin et al. show that dense passage retrieval can outperform traditional sparse retrieval in open-domain question answering by embedding questions and passages into a shared vector space [2]. MARA will use this idea through vector indexes and embedding models, with hybrid or reranking options where useful.

Recent RAG surveys emphasise that RAG can reduce hallucination, improve factual grounding and make language-model applications easier to update [3]. However, retrieval quality, chunking strategy and evaluation remain difficult. For this reason, MARA will not treat the language model as the whole solution. It will expose retrieved evidence, show citations, support page preview, and test retrieval separately from generation.

The UI is equally important because the user must inspect sources, not just receive an answer. Gradio is suitable because it supports Python-first interactive interfaces with upload controls, chat components, preview panels and settings [4]. The design will follow a workbench style because the target use case is repeated document analysis.

OWASP's guidance on LLM applications highlights risks such as sensitive information disclosure and prompt injection [5]. MARA will reduce these risks by using local storage by default, avoiding unnecessary personal data collection, warning users not to upload confidential third-party material during evaluation, and testing on public or synthetic documents.

## Development and Implementation Summary

The project will be implemented mainly in Python 3.10+. The existing repository has three main layers: `kotaemon` provides LLM wrappers, document loaders, vector stores, indexing and retrieval; `ktem` provides the application runtime, Gradio UI, settings, database models, page preview and DocQA orchestration; and `slide-cli` exposes the public `slide` command line interface. This structure will be preserved because it separates core RAG logic, application services and user-facing commands.

Development will begin with background reading and a review of the current codebase. I will then stabilise the baseline application, define a small evaluation document set, and improve the workflow in increments: ingestion, retrieval, cited answers, page preview, knowledge graph interaction, and UI polish. Each change will be tested with targeted unit or integration tests before wider regression checks. Git will be used for version control and a short development log.

The main workflow will be:

1. Load or upload documents through the web UI or CLI.
2. Extract text and metadata from each file.
3. Split documents into chunks and store them in a document store.
4. Generate embeddings and store them in a vector store.
5. Retrieve relevant chunks for a user question.
6. Pass the retrieved context to the language model.
7. Display the answer, citations, retrieved evidence and preview links.
8. Build or refresh a conversation knowledge graph for follow-up exploration.

## Data Sources

The project will use three kinds of data. First, it will use public or open-licence documents for development and demonstration, such as academic papers, technical documentation or synthetic reports. These will be used only where permitted and cited if they appear in the dissertation. Second, the application may process non-sensitive documents uploaded by the developer during testing. Third, evaluation will generate participant feedback, such as task success notes, Likert-scale ratings and short comments.

The project will not require scraping private websites, collecting personal records, or storing confidential user documents. If participants are involved, they will use a prepared public/synthetic document set rather than their own private files. Feedback will be anonymised, stored securely, and reported only in aggregate.

## Testing and Evaluation

Technical testing will show that the software works as intended. Unit tests will cover parsing, indexing, retrieval routing, citation construction, CLI commands and knowledge graph services. Integration tests will check that a document can be indexed, queried and cited through the shared runtime. Manual UI testing will verify upload, chat, preview, citation navigation, graph generation and theme behaviour. Benchmark questions will be used where possible to check whether retrieved evidence contains the expected answer-bearing passages.

Evaluation will focus on whether MARA meets the original requirements. I plan to run a small usability evaluation with adult volunteers, using public or synthetic documents. Participants will complete tasks such as uploading a document, asking for a summary, locating a cited page, comparing sources, and using the knowledge graph to create a follow-up question. I will record task completion, visible errors, time taken where useful, and anonymous feedback about clarity, trust and ease of use.

## Project Ethics and Human Participants

The planned human participant activity is a low-risk usability evaluation with adult volunteers only. Participants will receive an information sheet explaining the purpose, tasks, collected data, and withdrawal process before submission of the anonymised analysis. No vulnerable participants will be recruited, and no participant will be asked to upload private, personal or sensitive documents.

The evaluation data will be limited to anonymised task results, ratings and optional comments. Names, emails and raw identifiers will not be included in the dissertation. Any direct quote will be anonymised and checked. Data will be stored in a password-protected location and deleted after the course retention period. If the scope changes, I will seek supervisor approval before collecting new data.

## BCS Project Criteria

| BCS outcome                     | How this project will address it                                                                                                                    |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Practical and analytical skills | The project applies Python development, software testing, information retrieval, UI design and evaluation methods learned during the degree.        |
| Innovation or creativity        | The creative element is the combination of local RAG, citation preview and knowledge graph exploration in one research workbench.                   |
| Synthesis and evaluation        | The solution combines literature on RAG, dense retrieval, UI design and software engineering, then evaluates the result technically and with users. |
| Real need in a wider context    | Students and knowledge workers often need to understand large document collections while checking source evidence.                                  |
| Self-management                 | The project will be planned through milestones, version control, tests, risk tracking and dissertation writing time.                                |
| Critical self-evaluation        | The final dissertation will reflect on design decisions, failed approaches, limitations of retrieval accuracy, and future improvements.             |

## UI/UX Mockup

The intended interface will be a document analysis workbench rather than a simple chatbot. A rough wireframe is shown below.

```text
+--------------------------------------------------------------------------------+
| MARA                         Chat | File Index | Resources | Settings | Theme   |
+--------------------------------------------------------------------------------+
| Conversations / Sources      | Chat with documents             | Evidence       |
| -----------------------      | ------------------------------  | -------------- |
| + New conversation           | User: What are the key points?  | Citation 1     |
| Search all files             | MARA: Summary with [1] [2]      | page preview   |
| [x] report.pdf               |                                | highlighted    |
| [ ] notes.docx               | Ask a follow-up... [Send]       | source text    |
|                              |                                  |                |
| File Index                   | Knowledge Graph Preview         | Graph Context  |
| Upload and Index             | [Open fullscreen graph]         | selected node  |
+--------------------------------------------------------------------------------+
```

The left panel supports conversation and source selection. The centre panel is the main chat flow. The right panel shows evidence, citation targets and document preview. The knowledge graph preview will open into a larger viewer so users can pan, zoom and click nodes without losing the chat context.

## Project Plan

| Stage                                   | W1  | W2  | W3  | W4  | W5  | W6  | W7  | W8  | W9  | W10 | W11 | W12 |
| --------------------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Background reading and proposal         | X   | X   |     |     |     |     |     |     |     |     |     |     |
| Baseline setup and code review          |     | X   | X   |     |     |     |     |     |     |     |     |     |
| Data set and evaluation design          |     |     | X   | X   |     |     |     |     |     |     |     |     |
| Ingestion/retrieval improvements        |     |     |     | X   | X   |     |     |     |     |     |     |     |
| Citation and preview workflow           |     |     |     |     | X   | X   |     |     |     |     |     |     |
| Knowledge graph/UI refinement           |     |     |     |     |     | X   | X   | X   |     |     |     |     |
| Automated testing and benchmark checks  |     |     |     |     | X   | X   | X   | X   | X   |     |     |     |
| User evaluation                         |     |     |     |     |     |     |     | X   | X   |     |     |     |
| Analysis, dissertation and presentation |     |     |     |     |     |     |     |     | X   | X   | X   | X   |

## Risks and Contingency Plans

| Risks                                            | Contingencies                                                                                  | Likelihood | Impact |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ---------- | ------ |
| Retrieval quality is too weak for useful answers | Build a small benchmark set, tune chunking/retrieval settings, and report limitations honestly | Medium     | High   |
| LLM API cost or availability problems            | Support local models and keep tests independent of paid APIs where possible                    | Medium     | Medium |
| Document conversion fails for some formats       | Prioritise PDF, text and Markdown; treat Office preview as desirable if time is short          | Medium     | Medium |
| UI becomes too complex for users                 | Use a simple workbench layout and evaluate with task-based usability testing                   | Medium     | Medium |
| Running out of time                              | Prioritise essential requirements: upload, index, chat, citation and evaluation                | Medium     | High   |
| Hardware or data loss                            | Use Git, remote backups and exported evaluation data copies                                    | Low        | High   |
| Participant recruitment is delayed               | Use fewer participants and strengthen technical evaluation with benchmark tasks                | Medium     | Medium |
| Ethical scope changes unexpectedly               | Stop collection and confirm revised plans with the supervisor before proceeding                | Low        | High   |

## References

[1] P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS, 2020. Available: https://arxiv.org/abs/2005.11401

[2] V. Karpukhin et al., "Dense Passage Retrieval for Open-Domain Question Answering," EMNLP, 2020. Available: https://arxiv.org/abs/2004.04906

[3] Y. Gao et al., "Retrieval-Augmented Generation for Large Language Models: A Survey," arXiv, 2023. Available: https://arxiv.org/abs/2312.10997

[4] Gradio, "Gradio Documentation." Available: https://www.gradio.app/docs

[5] OWASP Foundation, "OWASP Top 10 for Large Language Model Applications." Available: https://owasp.org/www-project-top-10-for-large-language-model-applications/

[6] Cinnamon, "Kotaemon: An Open-Source Tool for Chatting with Your Documents." Available: https://github.com/Cinnamon/kotaemon
