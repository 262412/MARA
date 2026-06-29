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

| Proposal 项                                                                                | 当前状态                 | 证据                                                                                                                                                  | 下一步                                                                                            |
| ------------------------------------------------------------------------------------------ | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 本地优先 Web/CLI DocQA runtime                                                             | 基本完成                 | `ktem.docqa.DocQARuntime`; Web 的 `build_web_docqa_request`; CLI 的 `MARA docqa` 命令族；Phase 1 live validation 已跑通                               | Phase 2 继续做 answer-quality protocol，不再把 request parity 作为阻塞项                          |
| 支持 PDF/Word/PPT/Excel/CSV/Markdown/plain text upload/index/query                         | 基本完成                 | `FileIndex` 默认类型覆盖 `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.md`, `.txt`, `.zip`; runtime indexing 支持目录和 zip 展开                       | 继续补 format robustness end-to-end 结果，特别是 PPTX/Excel/公式/图表                             |
| 稳定 `DocQARequest` / `DocQAResponse`                                                      | 基本完成                 | `libs/ktem/ktem/docqa/_runtime_models.py` 已定义完整模型；Phase 1 已加入 CLI runtime adapter 与 Web/CLI parity tests                                  | 保持 contract tests；后续只在有迁移计划时改 public JSON/session/request shape                     |
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
- Element route 已完成两层工程修复: benchmark document metadata 可转为 request-level `element_index_records`；DocQA file index 支持同名离线 OCR/layout sidecar（`*.mara-elements.json` / `*.elements.json` / `*.layout.json`）持久化为 `mara_element_index` docs 和 `element_index` relation。
- GraphRAG claim 已限制为 `local_lightweight_only` / `full_graphrag_claim=false`，避免在完整 GraphRAG pipeline 尚未实现前过度表述。
- Public surface 影响已限制在 benchmark summary/report JSON/Markdown 字段、DocQA request adapter 字段、DocQA persisted element-index 行为和 sidecar 文件格式；未改变 MARA/MARA-cli 命令面、CLI options、DB schema、session shape 或 Gradio event chain。

最终证据摘要:

- Slurm larger-than-smoke run `9294899` 已完成: `20` examples x `5` routes = `100` predictions，`num_skipped_routes=0`，artifact 位于 `/mnt/scratch/users/tbczhang/outputs/MARA/phase3_multimodal_slurm/20260628_045247_phase3-slidevqa-multimodal-slurm-9294899`。
- 该 run 中 `page_image_rag_vlm` 为 `vlm_live`，F1/native `0.3911`, page hit `0.95`；`hybrid_rag` F1/native `0.3833`, page hit `0.85`；`controller_auto` F1/native `0.4161`, page hit `0.9`；`text_rag` 和 `element_rag` 均为 F1/native `0.0056`, page hit `0.0`。
- MMDocRAG persisted element-record probe 证明非 gold persisted records 能被 route 读取: `5/5` predictions 有 `element_index`，平均 `6.0` records/prediction。但质量未提升: `element_rag` F1/native `0.0286`, page hit `0.0`；matched `text_rag` F1/native `0.5053`, page hit `0.8`。
- 当前 manifest-level `slidevqa-test-shard0.multimodal.routes.json` 与 `mmdocrag-dev15.multimodal.routes.json` 仍产出 `element_records=0`；因此不能把现有 manifest 的 element route 结果写成真实非 gold OCR/layout 质量提升。

验证摘要:

- Benchmark / Phase3 tests: `benchmark/tests -q` 为 `250 passed`；Phase3 summary/report、Slurm assets、runtime helper、multimodal evidence 相关 tests 均通过。
- Route2 tests: offline layout sidecar 与 file-index element persistence 相关 tests 为 `45 passed`。
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
- Public surface 未改变: 未改 `MARA` / `MARA-cli` 命令面、CLI options、JSON keys、DB schema、DocQA session shape、用户文件格式或 Gradio event 语义。
- Baseline 债务未扩大，且未刷新 `scripts/codebase_hygiene_baseline.json`。

代表性验证:

- `uv run --python 3.10 pytest libs/ktem/ktem_tests/test_chat_layout_contract.py libs/ktem/ktem_tests/test_assets_theme.py libs/ktem/ktem_tests/test_workbench_layout_theme.py libs/ktem/ktem_tests/test_workbench_ui_contract.py libs/ktem/ktem_tests/test_studio_chat_page_bindings.py libs/ktem/ktem_tests/test_chat_docqa_runtime_adapter.py libs/ktem/ktem_tests/test_chat_preview_timer.py libs/ktem/ktem_tests/test_chat_message_events.py libs/ktem/ktem_tests/test_chat_source_scope.py libs/ktem/ktem_tests/test_chat_submission.py libs/ktem/ktem_tests/test_knowledge_graph_phase4b_builders.py`: `56 passed, 1 warning`。
- `uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>`: `No codebase hygiene ratchet violations.`。
- `uv run --python 3.10 python -m pre_commit run --files <changed-files>`: passed。
- Storage/layout: `.venv` 指向 `/mnt/fastscratch/users/tbczhang/envs/mara`，`.venv/bin/python` 指向 fastscratch uv Python；fastscratch/scratch quota 均低于 soft limit；repo 根目录没有 `data/`, `datasets/`, `outputs/`。

Residual risk / 后续维护:

- `ChatPage` class 仍然较大，仍聚合 preview、DocQA state、graph behavior、notebook/studio glue 等多条 workflow；`_render_chat_file_list_html` 和 `rerun_page_answer` 仍略高于 80 行 review trigger。这些是后续长期维护候选，不再阻塞 Phase 4 关闭。
- 后续继续控债时必须先锁定对应 Gradio workflow/DOM/source-string 契约，再按真实职责边界迁移；不能为了低于行数预算而压缩 fixture、删边界情况、降低 UI 稳定性或牺牲性能。

## 当前一句话结论

MARA 已经完成了 thesis prototype 的核心骨架：本地 Web/CLI runtime、Self-RAG-inspired controller contracts、route registry、evidence/trace schema、guardrail/verifier、multimodal route scaffolding、benchmark framework、Phase 1 public runtime contract、Phase 2 benchmark protocol engineering、Phase 3 multimodal workflow 和 Phase 4 UI/结构控债都已形成可维护闭环。真正未完成的是“研究结论级稳定性”：最终 thesis dataset/route/evaluator freeze、稳定 VLM route、大样本 failure analysis 和 paper-grade evaluator 还需要继续收口。
