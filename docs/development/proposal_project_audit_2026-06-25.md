# MARA proposal 项目梳理 - 2026-06-25

本报告基于 `docs/proposal_comp702.pdf` 和当前仓库状态，目标是把 proposal 中的研究/工程目标拆成四类：

- 已完成或基本完成
- 未完成或延期
- 需要进一步完善
- 需要重构

## 审计范围与约束

审计输入：

- Proposal: `docs/proposal_comp702.pdf`, 9 页, 创建时间 2026-06-10。
- 当前仓库: `/mnt/scratch/users/tbczhang/projects/MARA`。
- 关键参考文档: `docs/mara_thesis_mvp.md`, `README.md`, `docs/development/codebase-hygiene-contract.md`, `docs/development/storage-layout-contract.md`。
- 代表性 benchmark artifact:
  - `/mnt/scratch/users/tbczhang/outputs/MARA/artifacts/20260621_032814_plan5-financebench-10sample-formal-current-gpu-a100-lowbig-20260621-direct-answer-fix-small-seed`
  - `/mnt/scratch/users/tbczhang/outputs/MARA/artifacts/20260621_032234_plan5-qasper-10sample-formal-current-gpu-a100-lowbig-20260621-direct-answer-fix-small-seed`
  - `/mnt/scratch/users/tbczhang/outputs/MARA/artifacts/20260616_224239_plan5-slidevqa-50sample-visual-formal-l40s-20260616-p4-slide50-gpu-colvision`

环境状态：

- Repo 根目录正确: `/mnt/scratch/users/tbczhang/projects/MARA`。
- `.venv` 正确指向 `/mnt/fastscratch/users/tbczhang/envs/mara`。
- `.venv/bin/python` 指向 fastscratch uv Python: `/mnt/fastscratch/users/tbczhang/cache/uv/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10`。
- `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `HF_HOME`, `CODEX_HOME`, `KH_APP_DATA_DIR`, `TIKTOKEN_CACHE_DIR` 均在 scratch/fastscratch 合规位置。
- Repo 根目录没有 `data/`, `datasets/`, `outputs/`。
- Phase 0 后 `/mnt/fastscratch` 文件数为 `467050 / 500000`，已回到 soft file quota 以下。本轮只运行了一个 targeted CLI contract test，没有运行 model call、indexing、benchmark 或大文件生成。

## Proposal 要求矩阵

| Proposal 项                                                                                | 当前状态                 | 证据                                                                                                                                                  | 下一步                                                                                            |
| ------------------------------------------------------------------------------------------ | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 本地优先 Web/CLI DocQA runtime                                                             | 基本完成                 | `ktem.docqa.DocQARuntime`; Web 的 `build_web_docqa_request`; CLI 的 `MARA docqa` 命令族                                                               | 做 Web/CLI 请求模型一致性修复和真实 runtime 回归测试                                              |
| 支持 PDF/Word/PPT/Excel/CSV/Markdown/plain text upload/index/query                         | 基本完成                 | `FileIndex` 默认类型覆盖 `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.md`, `.txt`, `.zip`; runtime indexing 支持目录和 zip 展开                       | 继续补 format robustness end-to-end 结果，特别是 PPTX/Excel/公式/图表                             |
| 稳定 `DocQARequest` / `DocQAResponse`                                                      | 部分完成                 | `libs/ktem/ktem/docqa/_runtime_models.py` 已定义完整模型                                                                                              | `libs/slide_cli/slide_cli/docqa_request.py` 与 ktem runtime 模型发生字段漂移，需要统一或适配      |
| `RouteDecision`, `RetrieveDecision`, `EvidenceBundle`, `VerifyDecision`, `ControllerTrace` | 基本完成                 | `libs/ktem/ktem/docqa/controller.py`, `evidence.py`, `verification.py`                                                                                | 保持 contract tests，避免在 benchmark/Web/CLI 间重复实现                                          |
| route/executor registry                                                                    | 基本完成                 | `route_registry`, `executor_registry`, `workflow.py` 覆盖 direct/doc_text/page_image/element/graph/hybrid/abstain                                     | registry 与实际 backend readiness 需要在 UI/benchmark 中一致显示                                  |
| text RAG                                                                                   | 基本完成                 | 复用 existing DocQA text retrieval/generation; benchmark 有 `text_rag` route                                                                          | 当前质量仍弱，需作为 baseline 固化而不是继续无目标调参                                            |
| controller auto routing                                                                    | 部分完成                 | heuristic/structured planner path 已有; benchmark 有 `controller_auto`                                                                                | 当前 routing 仍偏 heuristic，route confusion 需要重新定义 expected route 或改 planner             |
| page-image RAG                                                                             | 部分完成                 | local smoke retriever, ColVision HTTP retriever, Qwen-VL generator adapter 已有                                                                       | 真实 ColPali/ColQwen/VLM 需要可复现启动脚本、health gate 和 dissertation 级实验                   |
| element RAG                                                                                | 部分完成                 | element record parser/ranker/index persistence 已有                                                                                                   | SlideVQA 中 element route 仍 0 retrieval/low F1，需强化表格/图/公式/slide element extraction      |
| lightweight GraphRAG                                                                       | 部分完成                 | local graph evidence selector, graph summary answer path, graph source scope 已有                                                                     | 不是完整 GraphRAG；需限定论文表述为 local graph route，并补 global/local 评估                     |
| hybrid RAG                                                                                 | 部分完成                 | weighted fusion/RRF/learned-ranker hook, M3DocRAG page-first selector 已有                                                                            | 在 FinanceBench/QASPER 中未稳定优于 text；需要按问题类型细分收益                                  |
| CRAG-style retrieval evaluator                                                             | 部分完成                 | `evaluate_retrieval_quality`, `retrieval_adequacy_issue`, retry/abstain path 已有                                                                     | 阈值和 false abstention 需调校；QASPER strict route 出现明显过度拦截信号                          |
| claim verification                                                                         | 部分完成                 | light/strict verifier, domain verifier registry, unsupported claim rewrite/abstain path 已有                                                          | 当前 verifier 是 token/规则级，不应宣称 paper-grade hallucination detection                       |
| citations, evidence metadata, compact trace                                                | 基本完成                 | `DocQAResponse` 包含 `agent_trace`, `evidence_metadata`, controller decisions, `evidence_bundle`, `workflow_plan`; Web answer/references 可渲染 trace | 内联 citation recall 目前多为 0，需要修复/解释 highlight vs inline 输出差异                       |
| benchmark harness and route ablations                                                      | 基本完成框架，评估未完成 | manifest v2, route matrix, route metrics, dataset-native score, proxy score 已有                                                                      | 外部 paper-grade evaluator 多数未配置；需要定稿正式 benchmark protocol                            |
| ALCE/MMDocRAG/RAGTruth-style metrics                                                       | 部分完成                 | local converters/evaluators/report fields 已有                                                                                                        | 当前 report 显示 external evaluators 多为 `not_configured`; 论文只能称 local adapted metrics      |
| Web UI workbench mockup                                                                    | 部分完成                 | source browser, preview, chat, route controls, trace, graph, Studio artifacts 已有                                                                    | proposal 中三栏 research workbench 仍需收敛 UI 信息架构和视觉一致性                               |
| Automated tests                                                                            | 部分完成                 | benchmark/ktem/slide_cli 有大量 targeted tests；Phase 0 已跑 `libs/slide_cli/tests/test_cli_contract.py`                                              | fastscratch 已回到 soft file quota 以下；后续改动按影响面跑 targeted tests，不建议直接跑完整 gate |

## 已完成或基本完成

1. 核心产品 surface 已形成。

   - `README.md` 和 CLI 代码都以 `MARA` / `MARA-cli` 作为公开入口。
   - `MARA docqa` 覆盖 index/files/delete/ask/chat/sessions/resume/sources/notes/artifacts。
   - `MARA app`, `MARA model`, `MARA platform` 也已经进入公开命令面。

2. 共享 DocQA runtime 已经落地。

   - Web 和 CLI 都进入 `DocQARuntime`，并复用 file index, session, selected sources, notes, artifacts, graph cache。
   - Runtime response 已包含 proposal 要求的 answer, citations/reference text, evidence metadata, controller decision, route decision, retrieve decision, verify decision, guardrail decision, controller trace, evidence bundle 和 workflow plan。

3. Controller contract 和 route registry 已经从 proposal 进入代码。

   - `RouteDecision`, `RetrieveDecision`, `ControllerTrace`, `EvidenceBundle`, `VerifyDecision` 已是 dataclass/API surface。
   - `route_registry()` 和 `executor_registry()` 已能描述 direct, text, page-image, element, graph, hybrid, abstain 路线。
   - `workflow.py` 已把 planner step/default route step 变成可记录的 workflow plan。

4. Self-RAG-inspired control semantics 已有程序级实现。

   - 当前没有训练 Self-RAG reflection-token model，这与 proposal 的 scope note 一致。
   - route selection, retrieval decision, evidence evaluation, retry, route switch, verify, revise/abstain 都已在程序层实现。

5. Benchmark 框架已经可用。

   - `benchmark/README.md` 定义 manifest v2, route matrix, direct/text/controller/hybrid/guarded routes。
   - 已有 FinanceBench/QASPER/RAGTruth/ALCE/SlideVQA/ViDoRe/MMDocRAG 等目录和 artifacts。
   - report 已区分 dataset-native local score, MARA diagnostic proxy score, external/paper-grade evaluator status。

6. Study artifact 能力已经超过 proposal MVP 的最低线。
   - 支持 study guide, quiz, flashcards, mindmap, slide outline, briefing doc, FAQ, timeline, custom report, data table, infographic, slide deck, audio overview, video overview。
   - 但 audio/video 当前是 script/plan-first，media export 需要 adapter，这一点和 `docs/mara_thesis_mvp.md` 的 out-of-scope/extension 表述一致。

## 未完成或应明确延期

1. Trainable/learnable router 未完成。

   - 当前 planner 主要是 heuristic/structured planner path。
   - Proposal 中 trainable router 本来属于 desirable/future work，可以保留为 dissertation future work。

2. Production-level Self-RAG/CRAG/ColPali/GraphRAG/MMDocRAG 复现未完成。

   - 当前更准确的表述是 Self-RAG-inspired controller + CRAG-style evaluator + local graph route + optional visual backends。
   - 不应在论文中宣称完整复现这些系统。

3. Paper-grade external evaluation 未完成。

   - 代表性 report 中 ALCE/MMDocRAG/RAGTruth/RAGAS external evaluators 大多显示 `not_configured`。
   - 目前能支撑的是 local adapted metrics 和 diagnostic proxy metrics。

4. Full GraphRAG 未完成。

   - 现有 graph route 是 local graph index/evidence selector 和 summary path。
   - 社区发现、全局 query-focused summarization、graph construction quality evaluation 仍需要单独定义。

5. Rich graph interaction 未完全完成。

   - 当前有 knowledge graph/mindmap/graph source persistence。
   - Proposal desirable 中 full-screen pan/zoom/filter/study-guide views 需要按论文 demo 的最低需求重新确认。

6. Real media artifact generation 未完成。
   - `audio_overview` 和 `video_overview` 是 script-only/scene-plan。
   - `mp3/mp4` export 明确需要 media export adapter。

## 需要进一步完善

1. Benchmark 质量指标目前不足以证明 controller 全面优于 text RAG。

   - FinanceBench 10-sample A100 run: `text_rag` native score 0.1, `controller_auto` 0.0, `crag_guarded` 0.0, `hybrid_rag` 0.0。
   - QASPER 10-sample A100 run: `text_rag` native score 0.2901, `controller_auto` 0.2721, `crag_guarded` 0.1671。
   - 结论应改成: framework 可以比较 routes；controller/hybrid 的收益还需要按 modality/question type 证明。

2. Visual route 有早期正向信号，但仍需要实验闭环。

   - SlideVQA 50-sample ColVision run: `page_image_rag_vlm` F1 0.1273, page hit 1.0；`text_rag` F1 0.0099, page hit 0.0。
   - 这支持“visual route 对 slide/page image QA 有潜力”，但还需要稳定 backend setup、复现实验脚本和 error analysis。

3. Element route 需要补强。

   - SlideVQA 50-sample 中 `element_rag` retrieval/evidence 基本为空，F1 与 text baseline 同为 0.0099。
   - 优先看 index 阶段是否真实持久化 table/figure/formula/slide elements，再看 ranker 和 evidence bundle。

4. Verification/guardrail 需要校准。

   - QASPER 10-sample 中 `crag_guarded` unsupported claim rate/abstention signal 明显高于 text/controller routes，说明 strict verifier 可能过度拦截。
   - 需要分开统计 true abstention, false abstention, unsupported-claim false positive。

5. Citation 输出需要明确 metadata citation 与 inline citation 的差异。

   - 多个 report 中 metadata citation recall 有值，但 inline citation recall/precision 为 0。
   - 论文和 demo 需要解释当前引用模式，或者修复 inline citation 输出路径。

6. UI research controls 与 CLI route controls 不完全对称。

   - CLI 暴露 visual retriever/generator, allowed route, planner model 等。
   - Web research controls 当前主要是 controller/route/verify/planner model；visual backend、allowed routes、verification domain 等仍不完整。

7. Runtime/model health 需要并入正式 demo preflight。
   - `MARA doctor` green 不一定代表选中的 local LLM/VLM endpoint 可用。
   - Demo script 应先检查 text LLM、embedding/reranker、VLM/ColVision、`KH_APP_DATA_DIR`、index DB/vectorstore。

## 需要重构或重点控债

1. Web/CLI request model 需要统一。

   - `libs/ktem/ktem/docqa/_runtime_models.py` 的 `DocQARequest` 包含 `planner_backend`, `verification_domain`, `page_image_records`, `max_context_length` 等字段。
   - `libs/slide_cli/slide_cli/docqa_request.py` 的同名 dataclass 缺少部分 runtime 字段。
   - `libs/ktem/ktem/docqa/_runtime_turn.py` 和 `_runtime_mara.py` 读取这些字段。若 CLI 传入 slide_cli 自己的 dataclass，存在字段漂移风险。
   - 建议: CLI 直接复用 ktem `DocQARequest`，或增加明确 adapter + parity tests。

2. Chat page 仍是最大结构风险。

   - `libs/ktem/ktem/pages/chat/__init__.py` 当前约 3487 行。
   - 它仍承载 UI construction, event binding, preview, DocQA state, graph behavior, notebook/studio glue。
   - Proposal 说 Web 应是 thin adapter；当前还未达到。

3. Knowledge graph 模块仍偏大。

   - `knowledge_graph_builder.py` 约 1404 行。
   - `knowledge_graph_renderer.py`, `knowledge_graph_service.py` 也偏大。
   - 后续 graph route 或 UI work 不应继续往这些文件堆逻辑，应按 builder/service/persistence/render/route adapter 拆分。

4. Preview/Office conversion broad exceptions 太多。

   - preview 相关文件仍有大量 `except Exception`。
   - 这对 thesis demo 风险很高：失败时容易变成“页面没有证据”而不是可诊断错误。
   - 建议只保留用户可恢复 fallback，并记录 source path, converter, output path, exception message。

5. File index event chain 仍需谨慎。

   - `libs/ktem/ktem/index/file/_events.py` 已从大 UI 文件中拆出，但 Gradio chain order 本身就是行为。
   - 后续改 upload/index/refresh/chat selection 时必须先加 characterization tests。

6. Benchmark runner/reporting 不能继续膨胀。
   - `benchmark/runner.py`, `benchmark/reports.py`, `benchmark/engines.py` 已接近或超过 hygiene baseline 风险区。
   - 新指标应优先进入 focused helper modules，不要继续扩展 runner/report 主体。

## 建议后续路线

### Phase 0 - 恢复可验证环境

目标: 在跑测试、index、benchmark 前先处理 file quota。

- 清理或归档 fastscratch 高文件数缓存，尤其是重复 `__pycache__`, old test caches, stale model/cache shards。
- 重新确认 `lfs quota -h -u tbczhang /mnt/fastscratch` 文件数低于 soft quota。
- 然后再运行 targeted tests。

执行记录:

- 已清理 fastscratch 中可再生成的 `uv` 包/构建/临时缓存: `cache/uv/.tmp*`, `archive-v0`, `builds-v0`, `sdists-v9`, `wheels-v6`。
- 已清理可再生成的 `pip` HTTP/selfcheck 缓存: `cache/pip/http-v2`, `cache/pip/selfcheck`。
- 未清理 `envs/`, `mara_runtime/`, Hugging Face cache、模型权重、dataset、benchmark artifacts 或正在运行服务可能使用的 GPU 编译缓存。
- 复查 `lfs quota -h -u tbczhang /mnt/fastscratch`: `148.4G / 500G`, `467050 / 500000` files。
- 复查 `.venv`: 仍指向 `/mnt/fastscratch/users/tbczhang/envs/mara`，Python 为 `3.10.20`。
- Targeted verification: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest libs/slide_cli/tests/test_cli_contract.py -q` 通过，`8 passed`。

### Phase 1 - 修复 public runtime contract

目标: 保证 Web/CLI/runtime 不漂移。

- 统一 `DocQARequest` 来源或加入 adapter。
- 增加 CLI ask/chat 走真实 `DocQARuntime._prepare_turn_execution` 的 regression test。
- 为 `planner_backend`, `verification_domain`, `page_image_records`, `max_context_length` 加 CLI/Web parity coverage。

### Phase 2 - 定稿 thesis benchmark protocol

目标: 把“框架能跑”变成“论文能解释”。

- 选择 2-3 个正式 dataset family: 一个 text-heavy, 一个 visual/page-heavy, 一个 hallucination/citation-heavy。
- 固定 routes: direct, text_rag, page_image_rag_vlm, element_rag where meaningful, hybrid, controller_auto, crag_guarded。
- 报告必须区分 local dataset-native, MARA proxy, external/paper-grade unavailable。
- 写 error taxonomy: retrieval miss, wrong page, missing span, citation miss, verifier over-abstention, route mismatch。

### Phase 3 - 强化 multimodal route

目标: 让 proposal 的 multimodal claim 有最小可证明闭环。

- Page-image: 固化 ColQwen/ColPali/Qwen-VL 启动和 health check，保留 evidence-only smoke 作为 fallback。
- Element: 优先解决真实 element index coverage，再优化 ranker。
- Hybrid: 按 question type 证明什么时候优于 text，而不是要求所有 dataset 全面胜出。
- Graph: 只承诺 local lightweight graph route，除非实现完整 GraphRAG pipeline。

### Phase 4 - UI 和结构控债

目标: 让 demo UI 稳定，不让 chat page 继续吸收业务逻辑。

- 抽出 ChatPage 的 request builder, event binding, source selection, preview, graph, studio artifact coordination。
- 每拆一个 workflow，先加 contract test，保持 Gradio chain order。
- UI 只负责构造 request 和渲染 response；controller/evidence/graph/benchmark 逻辑留在 services/runtime。

## 当前一句话结论

MARA 已经完成了 thesis prototype 的核心骨架：本地 Web/CLI runtime、Self-RAG-inspired controller contracts、route registry、evidence/trace schema、guardrail/verifier、multimodal route scaffolding 和 benchmark framework 都已存在。真正未完成的是“研究结论级稳定性”：route quality、visual/element/graph 深度、paper-grade evaluator、Web/CLI parity 和 UI/runtime 控债还需要系统化收口。
