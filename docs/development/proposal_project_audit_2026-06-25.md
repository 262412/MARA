# MARA proposal 项目梳理 - 2026-06-25

本报告基于 `docs/proposal_comp702.pdf` 和当前仓库状态，目标是把 proposal 中的研究/工程目标拆成四类：

- 已完成或基本完成
- 未完成或延期
- 需要进一步完善
- 需要重构

## 状态维护规则

本文档是 MARA proposal 项目梳理的状态总表，不是长期流水日志。

Phase 开发中可以在对应小节临时记录每一次开发的结论、验证和未满足目标。Phase 被视为结束后，必须清理这些过程记录，只保留最终总结：

- Phase 当前状态和关闭日期。
- 最终满足了哪些 proposal 目标，哪些仍未满足。
- 最终影响的 public surface。
- 最新一次代表性验证命令和结果。
- Storage/dataset layout 与 quota 最新状态。
- 证据入口路径，例如 scratch outputs、benchmark artifacts、logs 或 targeted test 输出目录。
- Residual risk 和下一阶段 follow-up。

临时失败尝试、重复 rerun、调试命令、逐轮开发细节应保留在 outputs/logs/artifacts 中；除非它们解释最终 residual risk，否则不应长期留在本文档正文。

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
- Phase 1 live validation 后 `/mnt/fastscratch` 为 `148.8G / 500G`, `467157 / 500000` files；`/mnt/scratch` 为 `51.13G / 2T`,
  `134654 / 300000` files，仍低于 soft quota。
- Qwen3-8B vLLM 已在 `8000` 监听；DocQA indexing/ask live validation 已完成，临时索引已清理，证据保留在
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase1_quality_validation/`。

## Proposal 要求矩阵

| Proposal 项                                                                                | 当前状态                       | 证据                                                                                                                                                                                                                      | 下一步                                                                                            |
| ------------------------------------------------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 本地优先 Web/CLI DocQA runtime                                                             | 基本完成                       | `ktem.docqa.DocQARuntime`; Web 的 `build_web_docqa_request`; CLI 的 `MARA docqa` 命令族；Phase 1 live validation 已跑通                                                                                                   | Phase 2 继续做 answer-quality protocol，不再把 request parity 作为阻塞项                          |
| 支持 PDF/Word/PPT/Excel/CSV/Markdown/plain text upload/index/query                         | 基本完成，fixture smoke 已落地 | `FileIndex` 默认类型覆盖 `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.md`, `.txt`, `.zip`; `benchmark/format_smoke_harness.py` 可生成 PDF/Word/PPTX/Excel/CSV/Markdown/text 小样本并做 deterministic indexing/query smoke | 后续补真实 DocQA live/Slurm end-to-end 结果，特别是复杂 PPTX/Excel/公式/图表                      |
| 稳定 `DocQARequest` / `DocQAResponse`                                                      | 基本完成                       | `libs/ktem/ktem/docqa/_runtime_models.py` 已定义完整模型；Phase 1 已加入 CLI runtime adapter 与 Web/CLI parity tests                                                                                                      | 保持 contract tests；后续只在有迁移计划时改 public JSON/session/request shape                     |
| `RouteDecision`, `RetrieveDecision`, `EvidenceBundle`, `VerifyDecision`, `ControllerTrace` | 基本完成                       | `libs/ktem/ktem/docqa/controller.py`, `evidence.py`, `verification.py`                                                                                                                                                    | 保持 contract tests，避免在 benchmark/Web/CLI 间重复实现                                          |
| route/executor registry                                                                    | 基本完成                       | `route_registry`, `executor_registry`, `workflow.py` 覆盖 direct/doc_text/page_image/element/graph/hybrid/abstain                                                                                                         | registry 与实际 backend readiness 需要在 UI/benchmark 中一致显示                                  |
| text RAG                                                                                   | 基本完成                       | 复用 existing DocQA text retrieval/generation; benchmark 有 `text_rag` route                                                                                                                                              | 当前质量仍弱，需作为 baseline 固化而不是继续无目标调参                                            |
| controller auto routing                                                                    | 部分完成                       | heuristic/structured planner path 已有; benchmark 有 `controller_auto`                                                                                                                                                    | 当前 routing 仍偏 heuristic，route confusion 需要重新定义 expected route 或改 planner             |
| page-image RAG                                                                             | 部分完成                       | local smoke retriever, ColVision HTTP retriever, Qwen-VL generator adapter 已有                                                                                                                                           | 真实 ColPali/ColQwen/VLM 需要可复现启动脚本、health gate 和 dissertation 级实验                   |
| element RAG                                                                                | 部分完成                       | element record parser/ranker/index persistence 已有                                                                                                                                                                       | SlideVQA 中 element route 仍 0 retrieval/low F1，需强化表格/图/公式/slide element extraction      |
| lightweight GraphRAG                                                                       | 部分完成                       | local graph evidence selector, graph summary answer path, graph source scope 已有                                                                                                                                         | 不是完整 GraphRAG；需限定论文表述为 local graph route，并补 global/local 评估                     |
| hybrid RAG                                                                                 | 部分完成                       | weighted fusion/RRF/learned-ranker hook, M3DocRAG page-first selector 已有                                                                                                                                                | 在 FinanceBench/QASPER 中未稳定优于 text；需要按问题类型细分收益                                  |
| CRAG-style retrieval evaluator                                                             | 部分完成                       | `evaluate_retrieval_quality`, `retrieval_adequacy_issue`, retry/abstain path 已有                                                                                                                                         | 阈值和 false abstention 需调校；QASPER strict route 出现明显过度拦截信号                          |
| claim verification                                                                         | 部分完成                       | light/strict verifier, domain verifier registry, unsupported claim rewrite/abstain path 已有                                                                                                                              | 当前 verifier 是 token/规则级，不应宣称 paper-grade hallucination detection                       |
| citations, evidence metadata, compact trace                                                | 基本完成                       | `DocQAResponse` 包含 `agent_trace`, `evidence_metadata`, controller decisions, `evidence_bundle`, `workflow_plan`; Web answer/references 可渲染 trace                                                                     | 内联 citation recall 目前多为 0，需要修复/解释 highlight vs inline 输出差异                       |
| benchmark harness and route ablations                                                      | 基本完成框架，评估未完成       | manifest v2, route matrix, route metrics, dataset-native score, proxy score, paper-grade evaluator readiness metadata 已有                                                                                                | 外部 paper-grade evaluator 多数未配置；需要定稿正式 benchmark protocol                            |
| ALCE/MMDocRAG/RAGTruth-style metrics                                                       | 部分完成                       | local converters/evaluators/report fields 与 paper-grade readiness/blocker 字段已有                                                                                                                                       | 当前 report 显示 external evaluators 多为 `not_configured`; 论文只能称 local adapted metrics      |
| Web UI workbench mockup                                                                    | 部分完成                       | source browser, preview, chat, route controls, trace, graph, Studio artifacts 已有                                                                                                                                        | proposal 中三栏 research workbench 仍需收敛 UI 信息架构和视觉一致性                               |
| Automated tests                                                                            | 部分完成                       | benchmark/ktem/slide_cli 有大量 targeted tests；Phase 0 已跑 `libs/slide_cli/tests/test_cli_contract.py`                                                                                                                  | fastscratch 已回到 soft file quota 以下；后续改动按影响面跑 targeted tests，不建议直接跑完整 gate |

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

## 无需实际 benchmark 的工程收口项 [已完成]

以下项目已经通过代码契约、artifact/report schema、runbook 或 audit claim 边界完成工程收口。它们不再列为“未完成问题”；剩余工作只是在真实 benchmark/rerun、论文实验表格或 demo 演练中使用这些能力。

| 收口项                                  | 最终结论                                                                                                                                                   | 后续只剩什么                                                                           |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 最终论文 claim 边界                     | 已在本 audit 中冻结 completed artifacts、local adapted diagnostics、future work/out-of-claim 三类边界                                                      | 写论文时按该边界引用 artifacts，不把 local diagnostics 写成 official/paper-grade claim |
| Route matrix / evaluator authority 草案 | 已记录 route matrix draft、score authority hierarchy、dataset primary metric draft 和 promotion rule                                                       | 最终 thesis 主数据集/正式 dissertation table 仍需后续大样本结果决定                    |
| Paper-grade evaluator 接口准备          | 接口已支持 evaluator metrics + metadata，并在 prediction/summary/report 中保留 `paper_grade_ready`, `paper_grade_blockers`, `primary_metric`               | 真实 external evaluator 配置和 paper-grade score 仍需单独运行                          |
| Citation 输出路径和 schema 一致性       | metadata citation、inline citation、scored citation 与 evidence trace locator 字段已统一进入 artifacts                                                     | citation quality / attribution 仍需在主数据集 rerun 后解释                             |
| CRAG / verifier 可观测性                | true/false abstention、unsupported claim、retry、route switch 已进入 prediction、summary、route CSV 和 report                                              | verifier threshold / false positive calibration 仍需主数据集分析                       |
| VLM / multimodal runbook 产品化         | 8000/8001/8002/8003 health check、Slurm template、backend metadata logging、failure taxonomy 已固化                                                        | 仍需更大样本 VLM rerun 和稳定性/latency/failure distribution 结果                      |
| Element index 工程契约                  | OCR/layout sidecar schema、DocQA persisted element index 接入契约、coverage report 和 fixture-level tests 已补齐                                           | 仍需真实非 gold OCR/layout corpus 上证明 element route 的质量收益                      |
| Format robustness 测试框架              | PDF/Word/PPTX/Excel/CSV/Markdown/text fixture-level indexing/query smoke harness 已建立                                                                    | 真实复杂 PPTX/Excel/formula/chart 的 dissertation-level E2E 成功率仍需后续 benchmark   |
| Failure taxonomy / routing taxonomy     | prediction、summary、report 已输出 answer mismatch、timeout、backend unavailable、empty retrieval、false abstention、bad citation 与 route family taxonomy | 大样本 failure analysis 仍需使用该 taxonomy 汇总                                       |
| Desirable / future work 清理            | trainable router、full GraphRAG、rich graph UI、media export 已归类为 future work 或 scoped extension                                                      | 论文中只作为 extension/future work，不写成当前 completed artifact                      |

## Scoped extension / future work 边界

这些条目属于 proposal 的 desirable scope、后续 thesis extension 或 dissertation future work，不是 Phase 0-4 工程闭环的阻塞项，也不能写成当前 completed artifact。

| 项目                                                 | 当前分类                           | 当前可写 claim                                                                                             | 不能写成                                                                    |
| ---------------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Trainable / learnable router                         | Future work                        | 当前是 heuristic / structured planner path；可写成 route-aware controller prototype                        | 已训练 Adaptive-RAG / MAO-ARAG-style router                                 |
| Full GraphRAG                                        | Scoped extension                   | 当前是 local lightweight graph route / graph evidence / summary path                                       | 完整 GraphRAG，包括 community detection、global query-focused summarization |
| Rich graph UI                                        | Scoped UI extension                | 当前有 knowledge graph / mindmap / source scope                                                            | full-screen pan/zoom/filter/study-guide graph workbench                     |
| Real media artifact export                           | Scoped media extension             | 当前 audio/video overview 是 script/plan-first artifact                                                    | 真实 `mp3/mp4` media export                                                 |
| Production-level Self-RAG/CRAG/ColPali/MMDocRAG 复现 | Future work / out of current claim | 当前实现是 Self-RAG-inspired controller、CRAG-style evaluator、local graph route、optional visual backends | 完整复现这些 production/research systems                                    |

## 仍需要真实实验或论文结果支撑的项目

1. Paper-grade external evaluator 的真实配置/运行尚未完成。

   - 代表性 report 中 ALCE/MMDocRAG/RAGTruth/RAGAS external evaluators 大多显示 `not_configured`。
   - Evaluator 接口准备已经关闭: artifacts/report 会记录 `paper_grade_ready`, `paper_grade_blockers`, `primary_metric`, `contract_id`。
   - 目前能支撑的是 local adapted metrics 和 diagnostic proxy metrics；不能把接口 readiness 写成真实 paper-grade score。

## 需要进一步完善

1. Benchmark 质量指标目前不足以证明 controller 全面优于 text RAG。

   - FinanceBench 10-sample A100 run: `text_rag` native score 0.1, `controller_auto` 0.0, `crag_guarded` 0.0, `hybrid_rag` 0.0。
   - QASPER 10-sample A100 run: `text_rag` native score 0.2901, `controller_auto` 0.2721, `crag_guarded` 0.1671。
   - 结论应改成: framework 可以比较 routes；controller/hybrid 的收益还需要按 modality/question type 证明。

2. Visual route 有早期正向信号，runbook 已产品化，但仍需要实验闭环。

   - SlideVQA 50-sample ColVision run: `page_image_rag_vlm` F1 0.1273, page hit 1.0；`text_rag` F1 0.0099, page hit 0.0。
   - 8000/8001/8002/8003 health check、Slurm template、backend metadata logging 和 failure taxonomy 已固化。
   - 这支持“visual route 对 slide/page image QA 有潜力”，但还需要更大样本、稳定 latency 和 error analysis。

3. Element route 工程契约已关闭，但质量仍需补强。

   - SlideVQA 50-sample 中 `element_rag` retrieval/evidence 基本为空，F1 与 text baseline 同为 0.0099。
   - OCR/layout sidecar schema、persisted index 接入、coverage report 与 fixture-level tests 已完成。
   - 后续重点转为真实非 gold sidecar corpus rerun、ranker/coverage 和 answer-quality analysis。

4. Verification/guardrail 可观测性已关闭，但仍需要校准。

   - QASPER 10-sample 中 `crag_guarded` unsupported claim rate/abstention signal 明显高于 text/controller routes，说明 strict verifier 可能过度拦截。
   - 当前 benchmark 已补 CRAG/verifier observability 字段和报告: `true_abstention`, `false_abstention`, `unsupported_claim_count`, `retry_count`, `route_switch_count` 会进入 prediction、summary、route CSV 和 report markdown。
   - 剩余工作是按主数据集分析 true/false abstention、unsupported-claim false positive/negative，并校准阈值；这次修复不等同于 verifier 质量已经达标。

5. Citation 输出质量需要继续解释，但 schema/path consistency 已关闭。

   - 多个 report 中 metadata citation recall 有值，但 inline citation recall/precision 为 0。
   - 当前 benchmark artifact schema 已保持 metadata citation、inline citation 和 evidence trace locator 字段一致: `predicted_sources`, `predicted_citations`, `scored_predicted_sources` 会进入 prediction 与 retrieval trace，evidence item 的 `citation`/`source` locator 会规范化为 `source_backrefs`。
   - 论文和 demo 仍需要解释 metadata citation 与 inline citation 的指标差异；这次修复不等同于 paper-grade attribution。

6. UI research controls 与 CLI route controls 不完全对称。

   - CLI 暴露 visual retriever/generator, allowed route, planner model 等。
   - Web research controls 当前主要是 controller/route/verify/planner model；visual backend、allowed routes、verification domain 等仍不完整。

7. Runtime/model health 已产品化到 runbook，但仍需要正式 demo preflight 演练。
   - `MARA doctor` green 不一定代表选中的 local LLM/VLM endpoint 可用。
   - Runbook / Slurm template 已能检查 text/VLM/retrieval/ColVision backend；正式 demo script 仍应先检查 text LLM、embedding/reranker、VLM/ColVision、`KH_APP_DATA_DIR`、index DB/vectorstore。

## 需要重构或重点控债

1. Web/CLI request model 已完成 Phase 1 收口，后续仍需防漂移。

   - `libs/ktem/ktem/docqa/_runtime_models.py` 的 `DocQARequest` 包含 `planner_backend`, `verification_domain`, `page_image_records`, `max_context_length` 等字段。
   - Phase 1 已为 `libs/slide_cli/slide_cli/docqa_request.py` 增加 runtime adapter，并补齐 CLI/Web parity coverage。
   - 当前风险不再是已知字段缺失，而是后续新增 request/session/JSON 字段时再次出现 Web/CLI/runtime 漂移。
   - 后续要求: 任何 DocQA public request shape 变更都必须同步更新 CLI/Web parity tests 和 live-record 执行记录。

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

### Phase 0 - 恢复可验证环境 [已完成]

目标: 在跑测试、index、benchmark 前先处理 file quota。

最终结论:

- 2026-06-25 已关闭。fastscratch 文件数已回到 soft quota 以下，仓库重新进入可验证状态。
- 清理范围只包含可再生成缓存，包括 `uv` 包/构建/临时缓存和 `pip` HTTP/selfcheck 缓存；未清理 `envs/`, `mara_runtime/`, Hugging Face cache、模型权重、dataset、benchmark artifacts 或正在运行服务可能使用的 GPU 编译缓存。
- `.venv` 保持为指向 `/mnt/fastscratch/users/tbczhang/envs/mara` 的 symlink，repo 根目录未放置 `data/`, `datasets/`, `outputs/`。
- 代表性验证: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest libs/slide_cli/tests/test_cli_contract.py -q` 通过，`8 passed`。
- Residual risk: 后续所有 `uv`, tests, model call, DocQA indexing, dataset sync, Slurm 前仍必须执行 storage/dataset preflight；fastscratch file quota 仍是常态风险。

### Phase 1 - 修复 public runtime contract [已完成]

目标: 保证 Web/CLI/runtime 不漂移。

最终结论:

- 2026-06-27 已关闭。Public runtime contract 不再阻塞 Phase 2；后续工作转入 answer-quality protocol、route quality 和 backend 深度验证。
- CLI `MARA docqa ask/chat` 在调用 runtime 前会转换为 canonical `ktem.docqa.DocQARequest`，避免 CLI/Web/runtime request shape 漂移。
- CLI/Web parity 已覆盖 `planner_backend`, `verification_domain`, `page_image_records`, `max_context_length`；CLI 也暴露了相应 options。
- Live quality validation 证明: 用户侧默认 `mara` reasoning 更适合解释型回答；benchmark 侧必须使用独立 answer-only prompt/policy，不能用用户解释型回答直接作为 exact/F1 主评测输出。
- Public surface 影响: `MARA docqa ask/chat` options 与 Web request builder 字段传递被补齐；未改变 DB schema、session shape 或 Gradio event chain。
- 证据入口: `/mnt/scratch/users/tbczhang/outputs/MARA/phase1_quality_validation/`。
- Residual risk: 未来任何 DocQA public request/session/JSON 字段变更，都必须同步更新 CLI/Web/runtime parity tests。

### Phase 2 - benchmark protocol engineering [已完成；thesis freeze pending]

目标: 把“框架能跑”变成“论文能解释”。

最终结论:

- 2026-06-27 工程阶段已关闭；最终 thesis dataset/route/evaluator freeze 仍 pending。此阶段关闭的是 benchmark protocol engineering，不是论文最终分数。
- 产品用户回答和 benchmark 回答已明确分离: 用户侧保留解释型 `mara` prompt；benchmark 侧使用 `gold_answer_v1` + `/no_think` + answer-only policy。
- Benchmark config/CLI/manifest/artifact/summary/report 已支持 `benchmark_prompt_policy`, `benchmark_no_think`, Phase2 dataset decision, failure taxonomy, route timeout budget, VLM backend readiness metadata。
- 七个候选 dataset family 已完成同 seed 小样本 `gold_answer_v1` live rerun 和 matched `benchmark_v1 --benchmark-no-think` baseline: FinanceBench, QASPER, RAGTruth, ALCE, MMDocRAG, SlideVQA, ViDoRe。
- Provisional dataset matrix 已形成但不冻结最终 thesis 主数据集: QASPER/RAGTruth/MMDocRAG 暂为主候选，ALCE secondary，FinanceBench/SlideVQA/ViDoRe 保留为诊断或 blocked candidate。
- Controller/guarded timeout 缺口已工程化处理: artifact 会记录 `error_type=route_timeout` 和 `route_timeout_seconds`；FinanceBench matched timeout rerun 已完成，但 controller/guarded 仍慢且质量为 0。
- VLM route 已完成最小 live proof: SlideVQA `page_image_rag_vlm` limit2 为 2 predictions、0 error rows、avg F1/native 0.4000、page hit 1.0000；ViDoRe 已切到 answer-bearing ArxivQA family 并证明 full QA generation route 可跑，但质量仍为 0 且存在 2048 context limit。
- Report score authority 已固定为三层: external/paper-grade, local dataset-native, MARA proxy。当前代表性 artifacts 仍不能声称 paper-grade external score。

Public surface:

- 影响范围限于 benchmark CLI/config/manifest/prediction/retrieval trace/summary/report 字段。
- 未改变 MARA/MARA-cli 公开产品命令面、DocQA request/session/DB schema、Gradio event chain 或用户文件格式。

代表性证据入口:

- Gold-answer live rerun: `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_gold_answer_live/`。
- Matched baseline rerun: `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_matched_baseline/`。
- Phase2 protocol matrix: `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_protocol/`。
- Timeout fixed rerun: `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_timeout_rerun_fixed_20260627/`。
- VLM/ViDoRe rerun: `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_vlm/`。
- Gap analysis: `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_gap_analysis/phase2_gap_analysis_20260627.md`。

最新验证:

- `uv run --python 3.10 python -m pytest benchmark/tests/test_runner_route_execution.py -q`: `9 passed`。
- `uv run --python 3.10 python -m pytest benchmark/tests -q`: `238 passed`, `1 warning`。warning 为 pypdf/cryptography ARC4 deprecation。
- `uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>`: `No codebase hygiene ratchet violations.`。
- `uv run --python 3.10 python -m pre_commit run --files <changed-files>`: passed。
- Storage/layout: `.venv` 指向 `/mnt/fastscratch/users/tbczhang/envs/mara`，`.venv/bin/python` 指向 fastscratch uv Python；`/mnt/fastscratch` 与 `/mnt/scratch` 均低于 soft quota；repo 根目录没有 `data/`, `datasets/`, `outputs/`。

Residual risk / 下一阶段:

- 最终 2-3 个 thesis 主数据集不能现在冻结；需要更大样本、稳定 route 对比和可解释 failure class 后再定。
- 8001 Qwen3-VL health/serving 已转入 Phase 3 处理；Phase 2 不再把 VLM backend missing 作为 protocol 阻塞项。
- SlideVQA VLM 有 page hit 正向信号，但仍存在重复答案和 answer mismatch；ViDoRe full QA 可跑但答案质量仍不达标。
- Controller/hybrid/guarded 不能声称全面优于 text baseline；后续必须按 dataset/question type 分析收益。
- Paper-grade external evaluator 尚未配置，论文表述必须继续限制为 local adapted/native/proxy metrics。

### Phase 3 - 强化 multimodal route [架构/工作流完成；性能质量后续迭代]

目标: 让 proposal 的 multimodal claim 有最小可证明闭环，优先完成可复现架构、route 工作流、health gate、evidence 汇总和工程接入；具体性能提升与论文级指标作为后续迭代处理。

最终结论:

- Phase 3 可以按“架构与工作流目标完成”关闭。Page-image、Element、Hybrid/Controller、Graph scope 四条路线均已有可执行路径、health/report 证据或明确的 claim 边界。
- Phase 3 不能表述为“multimodal 质量目标完全达成”。当前证据支持的是工作流闭环和工程可复现，不支持声称所有 multimodal route 全面优于 text baseline。

已完成能力:

- Page-image route 已接入 `page_image_rag_vlm`，使用 ColQwen/ColPali + `local_qwen3_vl` 的 health gate；8001 Qwen3-VL 可在 GPU1 与 8000/8002/8003 共存，`/v1/models` health 返回 `Qwen/Qwen3-VL-8B-Instruct`。
- 已新增 Phase3 benchmark summary/report 字段，记录 page-image backend readiness、element index coverage、hybrid question-type metrics 和 graph scope。
- 已新增可复现 Slurm/runbook 入口，allocation 内检查或启动 8000/8001/8002/8003，并用 `gold_answer_v1` + `--benchmark-no-think` 跑 route-all。
- Element route 已完成工程契约固化: benchmark document metadata 可转为 request-level `element_index_records`；DocQA file index 支持同名离线 OCR/layout sidecar（`*.mara-elements.json` / `*.elements.json` / `*.layout.json`）持久化为 `mara_element_index` docs 和 `element_index` relation；OCR/layout sidecar schema、persisted index metadata contract、coverage report JSON/Markdown 与 fixture-level tests 已补齐。
- GraphRAG claim 已限制为 `local_lightweight_only` / `full_graphrag_claim=false`，避免在完整 GraphRAG pipeline 尚未实现前过度表述。
- Public surface 影响已限制在 benchmark summary/report JSON/Markdown 字段、DocQA request adapter 字段、DocQA persisted element-index 行为和 sidecar 文件格式；未改变 MARA/MARA-cli 命令面、CLI options、DB schema、session shape 或 Gradio event chain。

最终证据摘要:

- Slurm larger-than-smoke run `9294899` 已完成: `20` examples x `5` routes = `100` predictions，`num_skipped_routes=0`，artifact 位于 `/mnt/scratch/users/tbczhang/outputs/MARA/phase3_multimodal_slurm/20260628_045247_phase3-slidevqa-multimodal-slurm-9294899`。
- 该 run 中 `page_image_rag_vlm` 为 `vlm_live`，F1/native `0.3911`, page hit `0.95`；`hybrid_rag` F1/native `0.3833`, page hit `0.85`；`controller_auto` F1/native `0.4161`, page hit `0.9`；`text_rag` 和 `element_rag` 均为 F1/native `0.0056`, page hit `0.0`。
- MMDocRAG persisted element-record probe 证明非 gold persisted records 能被 route 读取: `5/5` predictions 有 `element_index`，平均 `6.0` records/prediction。但质量未提升: `element_rag` F1/native `0.0286`, page hit `0.0`；matched `text_rag` F1/native `0.5053`, page hit `0.8`。
- 当前 manifest-level `slidevqa-test-shard0.multimodal.routes.json` 与 `mmdocrag-dev15.multimodal.routes.json` 仍产出 `element_records=0`；因此不能把现有 manifest 的 element route 结果写成真实非 gold OCR/layout 质量提升。

验证摘要:

- Benchmark / Phase3 tests: `benchmark/tests -q` 为 `250 passed`；Phase3 summary/report、Slurm assets、runtime helper、multimodal evidence 相关 tests 均通过。
- Route2 / element contract tests: offline layout sidecar、persisted element index、coverage report 与 file-index element persistence 相关 tests 已覆盖；本次 targeted contract run 为 `31 passed`。
- Hygiene / pre-commit: changed Python files 无 codebase hygiene ratchet violations；pre-commit passed。
- Storage/layout: `.venv` 指向 `/mnt/fastscratch/users/tbczhang/envs/mara`，`.venv/bin/python` 指向 fastscratch uv Python；fastscratch/scratch quota 均在 soft limit 内；repo 根目录没有 `data/`, `datasets/`, `outputs/`。

后续迭代项:

- 性能与质量: element ranker/coverage、真实非 gold sidecar corpus rerun、VLM/hybrid timeout、重复答案、answer formatting、inline citation recall/precision。
- 论文表述: 目前只可声称 Phase3 架构/工作流闭环和局部 route 证据；不能声称 multimodal route 已全面优于 baseline。

### Phase 4 - UI 和结构控债 [已完成；2026-06-29 关闭]

目标: 让 demo UI 稳定，不让 chat page 继续吸收业务逻辑。

最终结论:

- Phase 4 可以关闭。本阶段指定的 UI/结构控债目标已经落实: ChatPage 不再继续吸收新增业务逻辑，主要 workflow 已按职责边界迁出，Gradio event chain 顺序通过 contract tests 锁定，broader UI 失败已修复。
- `on_register_events`, `submit_msg`, `chat_fn`, `on_building_ui`, file-index event registration 和 knowledge graph builder 的关键大函数均已拆到 focused helper modules；`ChatPage` 只保留兼容 wrapper、状态协调和 Gradio callback/组件挂接。
- UI construction 已由 `chat_layout.py` 承接；`on_building_ui` 为薄 wrapper。`chat_fn` 保留 Gradio callback public 签名，内部通过 `ChatCallbackInputs` 显式传递长输入，不用动态 `locals()` 或压缩参数来机械降行数。
- Source selection、chat submission、preview/message/conversation/auxiliary events、runtime streaming、KG file/hierarchy/legacy/map builder、file index event chains 均有 focused tests 或 characterization tests。
- Phase 开发阶段遗留的代码/测试/脚本文件名已清理为功能语义命名，例如 dataset decision protocol、multimodal route summary/report、DocQA request contract、KG builder components、multimodal route Slurm/runbook；历史 artifact schema key 和已生成输出路径保留兼容。
- Public surface 未改变: 未改 `MARA` / `MARA-cli` 命令面、CLI options、JSON keys、DB schema、DocQA session shape、用户文件格式或 Gradio event 语义。
- Baseline 债务未扩大，且未刷新 `scripts/codebase_hygiene_baseline.json`。

代表性验证:

- `uv run --python 3.10 pytest libs/ktem/ktem_tests/test_chat_layout_contract.py libs/ktem/ktem_tests/test_assets_theme.py libs/ktem/ktem_tests/test_workbench_layout_theme.py libs/ktem/ktem_tests/test_workbench_ui_contract.py libs/ktem/ktem_tests/test_studio_chat_page_bindings.py libs/ktem/ktem_tests/test_chat_docqa_runtime_adapter.py libs/ktem/ktem_tests/test_chat_preview_timer.py libs/ktem/ktem_tests/test_chat_message_events.py libs/ktem/ktem_tests/test_chat_source_scope.py libs/ktem/ktem_tests/test_chat_submission.py libs/ktem/ktem_tests/test_knowledge_graph_builder_components.py`: `56 passed, 1 warning`。
- `uv run --python 3.10 pytest tests/test_descriptive_file_names.py`: `1 passed`。
- `uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>`: `No codebase hygiene ratchet violations.`。
- `uv run --python 3.10 python -m pre_commit run --files <changed-files>`: passed。
- Storage/layout: `.venv` 指向 `/mnt/fastscratch/users/tbczhang/envs/mara`，`.venv/bin/python` 指向 fastscratch uv Python；fastscratch/scratch quota 均低于 soft limit；repo 根目录没有 `data/`, `datasets/`, `outputs/`。

Residual risk / 后续维护:

- `ChatPage` class 仍然较大，仍聚合 preview、DocQA state、graph behavior、notebook/studio glue 等多条 workflow；`_render_chat_file_list_html` 和 `rerun_page_answer` 仍略高于 80 行 review trigger。这些是后续长期维护候选，不再阻塞 Phase 4 关闭。
- 后续继续控债时必须先锁定对应 Gradio workflow/DOM/source-string 契约，再按真实职责边界迁移；不能为了低于行数预算而压缩 fixture、删边界情况、降低 UI 稳定性或牺牲性能。

## 最终论文 claim 边界（2026-06-29）

本节是后续 dissertation、proposal-facing report 和 demo narrative 的 claim 边界源。历史 benchmark artifacts / run reports 保持 provenance，不回写修改；论文或上层总结引用它们时必须套用以下边界。

核心 claim:

> MARA 是一个本地优先、route-aware、多模态文档问答研究原型，已实现 Web/CLI 共用 runtime、类型化 DocQA 请求/响应契约、可检查的 answer/evidence/citation/controller/verification artifacts、多路检索与推理 route、轻量 graph 与 multimodal route 工程链路、学习资料生成，以及用于 local diagnostic evaluation 的 normalized benchmark framework。

### 可以写成 completed system artifacts

- Web/CLI shared DocQA runtime，以及 `MARA` / `MARA-cli` / `MARA docqa` public command surface。
- `DocQARequest` / `DocQAResponse` typed contract，以及 answer、citation/reference、evidence metadata、controller decision、route decision、retrieve decision、verify decision、guardrail decision、controller trace、evidence bundle。
- Route registry / executor registry，以及 direct、text RAG、page-image VLM、element、hybrid、controller-auto、CRAG-style guarded、local graph、abstain 等 route family 的工程实现或模板。
- Self-RAG-inspired controller semantics: route selection、retrieve、evaluate evidence、retry、route switch、verify、revise/abstain。必须写成 inspired / controller semantics，不能写成 production-level Self-RAG reproduction。
- Benchmark harness: manifest v2、route matrix、benchmark prompt policy、`gold_answer_v1`、`/no_think`、score authority、timeout/failure/routing taxonomy、summary/report artifacts、offline rescoring。
- Multimodal route plumbing: VLM route health/readiness、visual retriever metadata、page-image records、element sidecar / persisted index path、request-level `element_index_records`。
- Local lightweight graph route / graph evidence / graph context。必须写成 local lightweight graph route，不能写成 full GraphRAG。
- Study artifact generation surface: study guide、quiz、flashcards、mindmap、slide outline、briefing doc、FAQ、timeline、custom report、data table、infographic、slide deck。Audio/video 只能写 script/plan-first，不能写成真实 `mp3/mp4` media export。

### 只能写成 local adapted diagnostics

- Generic EM / F1 / ANLS、answer token length、numeric match、formula match。
- Dataset-native local scores，例如 FinanceBench answer correctness、QASPER local answer/evidence score、ALCE local correctness/citation score、RAGTruth local hallucination-span-style score、SlideVQA/MMDocRAG local visual QA score、ViDoRe retrieval diagnostics。
- MARA diagnostic proxy score。它只能作为内部系统诊断，不能写成 external score、official score 或 leaderboard score。
- Citation / evidence diagnostics: citation metadata recall/precision、inline citation recall/precision、gold page/source/span hit、page/doc/span hit、element/table/figure/formula/slide hit。
- Route/controller diagnostics: route-level native/proxy/F1、route ranking、route confusion、selected vs recommended route、question-type split、backend status by route、failure taxonomy、routing taxonomy。
- Guardrail/verifier diagnostics: abstention、false abstention、unsupported claim、rewrite skipped、guardrail expectation match、CRAG-style failure counts/classes。
- Runtime/performance diagnostics: parse/index/retrieval/generation seconds、total seconds、cache mode、executed/skipped routes。

这些 metrics 可以用于解释系统行为、失败模式和后续优化方向；不能写成 paper-grade evaluator result、official benchmark score 或稳定 superiority claim。

### 必须排除在 final claim 外或写成 future work

- Paper-grade external evaluator results 和 official leaderboard score。
- Production-level Self-RAG、CRAG、GraphRAG、MMDocRAG reproduction。
- Trainable / learnable router。
- Full GraphRAG，包括 community detection、global query-focused summarization 和 graph construction quality evaluation。
- Production ColPali / ColQwen benchmark claim；当前只能写为 optional/local visual backend 或 retrieval diagnostic。
- Stable large-sample VLM performance；当前只能写已有 live/Slurm evidence 和 remaining failure modes。
- Element RAG 在真实非 gold OCR/layout corpus 上稳定提升 answer quality 的结论。
- Calibrated verifier thresholds、paper-grade attribution / hallucination evaluation。
- Dissertation-level format robustness proof，尤其是真实复杂 PPTX/Excel/formula/chart 的完整 E2E 成功率；当前只有 fixture-level indexing/query smoke，不能替代 live DocQA benchmark。
- Rich graph UI（full-screen pan/zoom/filter/study-guide views）。
- Real audio/video media export（`mp3/mp4` adapter）。
- Controller/hybrid/guarded 全局稳定优于 text RAG 的结论。最多按 dataset、question type、modality 报告局部收益和失败类型。

## Route matrix / evaluator authority freeze draft（2026-06-29）

本节冻结的是论文评测协议草案，不是最终 benchmark 结果、最终主数据集或最终性能结论。后续只有在出现新的系统改动、明确 regression target 或 paper-grade evaluator 配置后，才应重新打开大规模 rerun；否则以本草案约束报告口径，避免把 local diagnostics 写成 official benchmark claim。

### Route matrix draft

| Dataset family           | Headline routes                                                              | Diagnostic routes                                                | 不作为主结论                                                                 |
| ------------------------ | ---------------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| QASPER / ALCE / RAGTruth | `direct_answer`, `text_rag`, `hybrid_rag`, `controller_auto`, `crag_guarded` | `element_rag` only when element records exist                    | `page_image_rag_vlm`，除非样本有真实 image/page evidence                     |
| FinanceBench             | `direct_answer`, `text_rag`, `controller_auto`, `crag_guarded`               | `hybrid_rag`, numeric/error diagnostics                          | 不声称 controller/guarded 提升；当前更适合作为 numeric / finance stress test |
| SlideVQA / MMDocRAG      | `text_rag`, `page_image_rag_vlm`, `hybrid_rag`, `controller_auto`            | `element_rag` as coverage / element diagnostic                   | `element_rag` 不作为质量主结论，除非真实非 gold OCR/layout corpus 后证明提升 |
| ViDoRe                   | `colqwen_retriever_only`, `colpali_retriever_only`                           | full QA generation only when answer-bearing route/data are ready | 不写 full QA benchmark claim，除非后续新 artifact 支撑                       |
| Format robustness        | indexing/query smoke by file type                                            | loader / preview / OCR / layout failure taxonomy                 | 不写成正式 QA benchmark                                                      |

Reporting rule:

- `direct_answer` 是 diagnostic baseline，用于区分 no-retrieval answer behavior，不代表 user-facing MARA workflow。
- `text_rag` 是默认 retrieval baseline，也是当前多数 text dataset 的主要对照。
- `controller_auto`, `hybrid_rag`, `crag_guarded` 只能按 dataset、question type、modality 和 failure class 报告局部收益或失败；不能写成全局稳定优于 `text_rag`。
- `page_image_rag_vlm` 可作为 SlideVQA/MMDocRAG 的 multimodal route evidence，但必须同时报告 backend health、latency、timeout、answer mismatch 和样本规模。
- `element_rag` 当前主要是 element coverage / persistence / locator diagnostic；在真实非 gold OCR/layout corpus 证明质量提升前，不能作为 answer-quality headline route。

### Evaluator authority draft

| Authority level         | 用途                                                                                                                                                                                                                                   | 是否可做 headline                       |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `external_paper_grade`  | 真实外部 evaluator，`paper_grade=true`，有固定 evaluator version/config/primary metric                                                                                                                                                 | 可以，但当前代表性 artifacts 多数未配置 |
| `local_dataset_native`  | Dataset-family local scoring adapter，例如 FinanceBench correctness、QASPER local answer/evidence score、ALCE local correctness/citation score、RAGTruth local hallucination-span-style score、SlideVQA/MMDocRAG local visual QA score | 当前默认 headline                       |
| `mara_diagnostic_proxy` | MARA 内部系统诊断，覆盖 answer、evidence、citation、groundedness、controller、abstention、format behavior                                                                                                                              | 不能做最终 benchmark headline           |
| `generic_diagnostic`    | EM/F1/ANLS、page hit、citation recall、latency、failure class 等通用诊断                                                                                                                                                               | 只能解释行为和失败模式                  |

Promotion rule:

- 如果 external evaluator 已配置，且返回 `paper_grade=true` 与有效 `primary_metric`，headline score 使用 `external_paper_grade`。
- Evaluator 接口 readiness 已落实: prediction、summary 和 report 会记录 `paper_grade_ready` 与 `paper_grade_blockers`；常见 blocker 包括 `not_configured`, `not_paper_grade`, `missing_primary_metric`, `primary_metric_missing_from_metrics`, `failed`。
- 否则 headline score 使用 `local_dataset_native`，并在论文中明确标成 local adapted / dataset-native local result。
- `mara_diagnostic_proxy` 永远不能升级成 paper-grade、official 或 leaderboard score。
- `generic_diagnostic` 永远作为 secondary diagnostic，不替代 dataset-native headline。
- 历史 artifacts 如果缺少升级所需字段，不做 retroactive authority promotion；只能通过明确的 rescoring artifact 或新 run 产生新的 authority。

### Dataset primary metric draft

| Dataset      | Primary without external evaluator                  | Secondary diagnostics                                                                  |
| ------------ | --------------------------------------------------- | -------------------------------------------------------------------------------------- |
| FinanceBench | local answer correctness / native score             | numeric match, page hit, false abstention, wrong-source / wrong-page failure classes   |
| QASPER       | local answer F1 / native score                      | evidence hit, citation metadata recall, answer length, multi-point extraction failures |
| RAGTruth     | local hallucination / unsupported-claim style score | abstention, false abstention, rewrite skipped, unsupported claim diagnostics           |
| ALCE         | local correctness + citation-style score            | metadata citation recall/precision, inline citation recall/precision                   |
| SlideVQA     | local visual QA F1 / native score                   | page hit, VLM backend status, latency, answer mismatch, timeout                        |
| MMDocRAG     | local visual QA / native score                      | page hit, element coverage, citation recall, VLM context/timeout failures              |
| ViDoRe       | retrieval diagnostic score only                     | retriever hit / page evidence / MRR-like diagnostics when available；full QA 单独标注  |

### Freeze status

- Frozen now: protocol-level route categories, route reporting roles, evaluator authority hierarchy, score promotion rule, and dataset primary-metric draft.
- Not frozen yet: final 2-3 thesis main datasets, final route matrix for dissertation tables, final evaluator authority with paper-grade external scores, and any superiority claim over `text_rag`.

## 当前仍未完成清单（proposal 对照，2026-06-29）

以下清单基于 `docs/proposal_comp702.pdf` 的 essential/desirable/evaluation 要求与当前 Phase 0-4 关闭结论重新对照。无需实际 benchmark 的工程收口项已经移到上方“已完成”总结；本节只保留仍需要真实实验、论文结果或最终 demo 演练支撑的事项。

### Essential scope 中仍未完全完成

1. 最终 thesis dataset / route / evaluator freeze 尚未完成，草案已冻结。

   - Proposal 要求 benchmark 能比较 direct baseline、fixed text RAG、至少一个 multimodal route、controller-auto、hybrid retrieval 和 CRAG-guarded execution。
   - 当前 benchmark protocol 已可运行，上方已记录 route matrix / evaluator authority freeze draft；但最终 2-3 个 thesis 主数据集、dissertation tables 的正式 route matrix、正式 evaluator authority 仍未冻结。
   - 关闭条件: 在 freeze draft 基础上完成更大样本 matched rerun，确定主数据集和辅助诊断数据集，明确每个报告分数来自 external/paper-grade、local dataset-native 还是 MARA proxy。

2. Paper-grade external evaluation 尚未配置。

   - Proposal 目标包含 ALCE/MMDocRAG/RAGTruth-style metrics，用于 answer quality、citation quality、multimodal evidence support 和 hallucination risk。
   - 当前已完成 paper-grade evaluator 接口 readiness: backend 可返回 `metrics` + `metadata`，系统会保留 `paper_grade`, `primary_metric`, `contract_id`, `scoring_mode`，并输出 `paper_grade_ready` / `paper_grade_blockers` 到 prediction、summary 和 report。
   - 代表性 artifacts 中 external evaluator 仍多为 `not_configured`，所以当前只完成 local adapted/native/proxy metrics 与 paper-grade evaluator 接口准备。
   - 关闭条件: 配置并跑通至少一个 paper-grade 或明确可引用的外部 evaluator；如果不可行，论文必须把结论限制为 local adapted metrics。

3. Controller / hybrid / guarded 路线尚未证明稳定优于 text RAG。

   - Proposal 的核心研究问题是 Self-RAG-inspired controller 是否能通过选择 route、retry、verify、abstain 改善 DocQA。
   - 当前工程闭环已存在，但 FinanceBench/QASPER 等证据仍显示 controller、hybrid、guarded 没有稳定全面优于 text baseline，且 guarded/controller 存在 timeout 或 false abstention 风险。
   - 关闭条件: 按 dataset、question type、modality 分层报告收益和失败类型；不能只用全局平均分宣称 controller 有效。

4. Element RAG 的真实非 gold OCR/layout 路径仍未达到质量目标。

   - Proposal 要求 indexing layer 存储 element records，并支持 tables、figures、formulas、slide/page elements。
   - Element index 工程契约已经关闭: sidecar schema、persisted index 接入、coverage report 和 fixture-level tests 已有。
   - 仍未完成的是质量结论: manifest-level SlideVQA/MMDocRAG 仍出现 `element_records=0` 或质量无提升；MMDocRAG persisted records 能读取但 `element_rag` 质量低于 text baseline。
   - 关闭条件: 准备真实非 gold OCR/layout corpus，验证 element coverage、element hit、page hit 和 answer quality 至少在 element/table/figure 问题上有可解释收益。

5. Page-image / VLM route 仍需要正式 thesis 级稳定性验证。

   - Proposal 允许 page-image RAG 使用 smoke/local backends，但如果要写成 visual answering 结果，必须有 backend metadata 和真实 VLM 证据。
   - VLM/multimodal runbook 产品化已经关闭: health check、Slurm template、backend metadata logging 和 failure taxonomy 已有。
   - 当前 `page_image_rag_vlm` 已有 live proof 和 Slurm run 正向信号，但仍存在重复答案、answer mismatch、timeout/performance 和样本规模不足问题。
   - 当前 benchmark 已补统一 failure/routing taxonomy 字段和报告表，可把 answer mismatch、timeout、backend unavailable、empty retrieval、false abstention、bad citation、unsupported claim 与 route family 分开统计。
   - 关闭条件: 固定 VLM/visual retriever backend、完成更大样本 rerun、记录 backend health、latency、taxonomy distribution 和可复现实验命令。

6. Citation / attribution 质量还未达到 proposal 的完整 evaluation 目标。

   - Proposal 要求 citation precision/recall、attributable claim rate、unsupported claim rate 等指标。
   - Citation 输出路径和 schema 一致性已经关闭: metadata citation、inline citation、scored citation 与 evidence trace locator 字段已统一。
   - 历史 artifacts 需要 rerun/rescore 才会拥有最新 trace 字段；claim attribution 仍不是 paper-grade。
   - 关闭条件: 报告 metadata citation 与 inline citation 的差异；至少在主数据集上给出 citation quality 和 unsupported-claim 分析。

7. CRAG-style evaluator 与 claim verifier 仍需校准。

   - Proposal 要求 weak evidence 触发 retry、route switch 或 abstention，并报告 unsupported claims。
   - CRAG/verifier 可观测性已经关闭: observability 字段和报告脚本已补齐，可统计 true abstention、false abstention、unsupported claim、retry、route switch。
   - 当前 evaluator/verifier 仍是 lightweight/rule-level 版本，不等同于 calibrated paper-grade verifier。
   - QASPER/guarded 路线仍有过度拦截和 false abstention 风险。
   - 关闭条件: 基于新 observability 字段完成主数据集分析，分开报告 true/false abstention、unsupported-claim false positive/negative，并调校 threshold 或限制论文 claim。

8. Format robustness 的端到端证据还不完整。

   - Proposal essential requirement 包含 PDF、Word、PowerPoint、Excel/CSV、Markdown、plain text upload/index/query。
   - Format robustness 测试框架已经关闭: PDF/Word/PPTX/Excel/CSV/Markdown/text fixture-level indexing/query smoke harness 已有。
   - 当前仍缺少真实复杂 PPTX/Excel/公式/图表等格式的 dissertation-level end-to-end 成功率和失败分类。
   - 关闭条件: 对真实复杂样本跑 DocQA live/Slurm 小样本或正式 benchmark，并记录 preview/OCR/layout/loader 边界。

### Desirable / scoped extension 分类

这些项目不再列为当前必须完成的工程缺口，而是明确归入 scoped extension 或 future work。论文中可以把它们作为设计延展、后续研究方向或 demo 扩展计划，但不能写成当前系统已完成能力。

| Extension item                       | 分类                       | 当前状态                                                                            | 论文口径                                                             |
| ------------------------------------ | -------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Trainable / learnable router         | Future work                | 当前 router 是 heuristic / structured planner path，没有训练 router                 | 可写 future work；不能写成已实现 trainable router                    |
| Full GraphRAG                        | Scoped extension           | 当前是 local evidence selector / summary path，并限制 `full_graphrag_claim=false`   | 可写 local lightweight graph route；完整 GraphRAG 是 extension       |
| Rich graph interaction               | Scoped UI extension        | 当前有 knowledge graph / mindmap / source scope                                     | full-screen pan/zoom/filter/study-guide views 是 UI future work      |
| Real media artifact export           | Scoped media extension     | 当前 audio/video overview 是 script/plan-first                                      | `mp3/mp4` export 需要 media adapter，应写成 extension 或 future work |
| Production-level system reproduction | Future work / out of claim | 当前是 Self-RAG-inspired controller、CRAG-style evaluator、optional visual backends | 不能宣称完整复现 Self-RAG、CRAG、ColPali、GraphRAG、MMDocRAG         |

### Thesis-ready reporting 中仍未完成

1. 大样本 failure analysis 尚未完成。

   - 当前已有 small/mid-size live rerun、Slurm evidence 和统一 failure/routing taxonomy 输出，但最终 dissertation 仍需要在更大样本上按 route、modality、question type、backend status 汇总失败类别。

2. Routing accuracy / expected route 评估尚未定稿。

   - Proposal 计划 route-level ablations 和 routing accuracy。
   - 当前 route confusion/expected route 仍需要重新定义，或基于已完成的 routing taxonomy 做可解释报告。

3. Latency、cost、backend type 的正式表格尚未成为论文最终结果。

   - Benchmark 已有 backend metadata/performance 字段，但最终 thesis 表格仍需统一抽取、解释和冻结。

4. Demo preflight 尚未完全产品化。

   - Multimodal Slurm/runbook 已能检查 8000/8001/8002/8003；但正式 demo 前仍需要一键或清单式 preflight，覆盖 text LLM、embedding/reranker、VLM、ColVision、`KH_APP_DATA_DIR`、DB/vectorstore 和 selected dataset paths。

5. Dissertation writing 尚未完成，final claim 边界已冻结。

   - 本 audit 已明确 completed artifact、local adapted metrics、future work/out-of-claim 边界。
   - 仍需把这些边界落实到 dissertation 正文、tables、figures 和 demo narrative，避免把 smoke/backend-unavailable route 写成正式效果。

## 当前一句话结论

MARA 已经完成了 thesis prototype 的核心骨架：本地 Web/CLI runtime、Self-RAG-inspired controller contracts、route registry、evidence/trace schema、guardrail/verifier、multimodal route scaffolding、benchmark framework、Phase 1 public runtime contract、Phase 2 benchmark protocol engineering、Phase 3 multimodal workflow、Phase 4 UI/结构控债和 paper-grade evaluator 接口准备都已形成可维护闭环。最终论文应强 claim completed system artifacts 和 local diagnostic framework，弱 claim evaluation 结果；真正未完成的是“研究结论级稳定性”：最终 thesis dataset/route/evaluator freeze、稳定 VLM/element route 质量、citation/claim attribution、大样本 failure analysis 和真实 paper-grade evaluator 配置/运行还需要继续收口。
