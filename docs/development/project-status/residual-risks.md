# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-28

## 1. 当前结论

本轮从 `Dev` 提交
`5112c00beaffcea3e3f5b680a387a6a00f70fd7d` 开始复核和修复。复核报告指出的五个
直接 P0 均已补失败保护测试并完成代码修复：

1. calculation verifier 现在验证全部 `required_for_execution` slot，不再跳过
   `role="dimension"`；
2. `verified_evidence` 与实际输出的 `cited_evidence` 已拆开；
3. 普通 quality retry 不再发送空查询；
4. cross-page/comparison QueryPlan 不再使用单一泛化 support slot；
5. hybrid fusion 的 score trace 使用 canonical evidence identity，RRF 不再把
   reranker score 当作 first-stage retriever score。

这代表五个已知代码断点已经关闭，不代表数据集能力已经验收。当前仍没有使用本轮
代码生成新的 QASPER 159×3 或 FinanceBench 20×4 artifact，因此：

- **可以进入 2–5 条 smoke artifact 和两组聚焦验证；**
- **仍不建议直接运行全量 benchmark；**
- **不能声称 QASPER、FinanceBench 或最终 Phase G 指标已经达标。**

本轮没有提交 Slurm 任务，也没有修改公开 `MARA`、`MARA-cli` 或 `MARA docqa`
命令及参数。

## 2. 为什么 `5112c00` 仍未根治

`5112c00` 已经实质重构 Evidence Identity、去重、二次检索、rerank truthfulness
和 evidence-set selection，但当时的状态文档把“主链路已有实现”写成了“契约已经
闭合”。静态复核证明这个结论过早，原因是测试主要验证模块内行为，没有逐阶段验证
跨模块投影不变量：

- QueryPlan 声明了 dimension execution slot，但 calculation verifier 又按
  `role == "operand"` 过滤；
- verifier 产生的是 claim support，却被直接复制成 emitted citation；
- 二轮 retrieval 的 missing-slot 路径有 query，普通 quality retry 路径却没有；
- cross-page 类型存在，但一个 `support:cross_page` 无法表达左右两侧必须同时
  命中；
- RRF 排序使用 canonical identity，trace map 却继续使用父 `evidence_id`；
- learned reranker 已执行，但 backend/score/rank 没有进入统一 reranked stage。

这些都是同一类错误：类型或阶段在上游已经声明，下游又用旧字段重新解释。今后关闭
问题必须同时证明“声明、执行、投影、指标”四个位置使用同一契约，不能只证明其中一
个函数正确。

## 3. 本轮已完成且有代码证据的修复

| 项目                        | 当前实现                                                                                                                                                                               | 保护证据                                                                                                |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Dimension slot verification | 全部 execution-required slot 进入 verifier；dimension 与 operand 的 unit/scale/currency provenance 分角色验证，缺失时阻止验证通过                                                      | `test_required_dimension_slot_is_verified`、`test_missing_dimension_slot_blocks_execution_verification` |
| Citation stage semantics    | runtime verifier 只写 `verified_claim_support_evidence`；benchmark finalizer 根据实际 structured/inline citation 反向映射 `emitted_citation_evidence`，再赋给兼容字段 `cited_evidence` | `test_cited_evidence_comes_from_emitted_citations`                                                      |
| Generation context stage    | 新增 `generation_context_evidence`；旧 `used_evidence` 仅作为有显式 `stage_aliases` 的兼容字段；计算路径另记 `execution_operand_evidence`                                              | stage metric 与 calculation citation tests                                                              |
| Quality retry               | 查询按 `retrieval_query → planning question → prompt` 回退，并强制去除空白                                                                                                             | `test_quality_retry_query_is_never_empty`                                                               |
| Cross-page plan             | comparison 拆成 `support:left_subject` 和 `support:right_subject`；显式 page/across 问题要求不同 source-page locator；graph aggregate 按 backref 投影为 locator atoms                  | cross-page QueryPlan 与 graph route tests                                                               |
| QueryPlan state             | request 保存初始 planned plan；每次绑定后更新 request 中的 bound plan，并记录 `stage/state_version`                                                                                    | `test_bound_plan_stage_is_explicit_and_updates_request_state`                                           |
| Hybrid score identity       | weighted、RRF、learned 三个 score map 均以 `identity_of(item).key` 为 key                                                                                                              | `test_hybrid_item_scores_use_canonical_cell_identity`                                                   |
| Fusion/rerank separation    | RRF 只消费 first-stage retriever score；learned reranker 统一输出 backend、score、input identity 和 rank                                                                               | hybrid fusion tests                                                                                     |
| Reranker lineage            | 删除跨 source 的全局 text-hash lineage；只接受 canonical identity、alias 或 source-page-text                                                                                           | `test_reranker_lineage_rejects_global_text_only_match`                                                  |
| Identity canonicalization   | canonicalization 重新计算 identity；嵌入的旧 identity 只作为 expected value，不一致即报 contract error                                                                                 | `test_canonicalization_rejects_stale_embedded_identity`                                                 |
| Visual benchmark projection | 保留 bbox、caption、OCR、VLM、section/table title；浮点式 index 安全规范化，异常值不再抛错                                                                                             | index metadata tests                                                                                    |
| Trace truthfulness          | page-first trace 改名为 `ranked_pages` 并标明 `preview_only`；未实际执行的 RRF modality top-k 字段已删除                                                                               | m3docrag/hybrid tests                                                                                   |
| Neighbor expansion          | raw neighbor ID 与 canonical identity 通过 evidence aliases 对齐                                                                                                                       | `test_neighbor_alias_expansion_uses_canonical_identity`                                                 |

## 4. 当前验证证据

| 验证                   | 结果                                                                    |
| ---------------------- | ----------------------------------------------------------------------- |
| `libs/ktem/ktem_tests` | 1388 passed，45 warnings                                                |
| `benchmark/tests`      | 479 passed，6 warnings                                                  |
| 定向 P0/契约测试       | 全部通过                                                                |
| 存储布局               | `.venv` 位于 fastscratch；repo root 无 `data/`、`datasets/`、`outputs/` |
| fastscratch quota      | 141.5G/500G，447963/500000 files                                        |
| 新 benchmark artifact  | 尚无                                                                    |
| 新 Slurm 任务          | 未提交                                                                  |

测试结果证明当前代码不变量通过，不证明真实数据集指标或延迟达标。fastscratch inode
已接近软配额的 90%，提交聚焦任务前仍要再次预检，但当前没有超过配额。

## 5. 最新开放问题表

表中只保留当前真实未关闭事项。已经有代码和包级回归证明关闭的问题不再重复列为
“待修复”。

| ID                       | 优先级 | 状态                      | 根因与当前缺口                                                                                                                                | 关闭标准                                                                                                                     |
| ------------------------ | ------ | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| CONTRACT-ARTIFACT-001    | P0     | 待聚焦验证                | 五个 P0 只有代码和单元测试证据，尚无本轮真实 artifact；不能排除 runtime adapter 或模型输出再次破坏 stage lineage                              | 先跑每类 2–5 条 smoke，再完成 QASPER 159×3、Finance 20×4；identity/stage/citation contract violation 均为 0                  |
| FIN-ATOMIC-SUPPLY-011    | P0     | 代码已有，artifact 未证实 | parser 和 table adapter 已能产生 cell/span，但真实 PDF 的 wrapped row、局部 scale、period header 仍可能只供给父表或 page evidence             | 固定困难样例全部提供可回溯 atom；缺 operand/dimension 时不执行；execution citation 覆盖全部 operand                          |
| EVIDENCE-SET-BUDGET-024  | P1     | 未完成                    | 当前仍先统一截断最多 80 个 fused candidate，再在该集合内恢复 slot；排名 81 以后无法恢复。required slot 仍按顺序贪心，可能提前耗尽 page budget | 每个 required slot 有独立候选配额，加全局 relevance 与 structure 配额；联合满足 required coverage 后再选择 optional evidence |
| SCORE-CALIBRATION-025    | P1     | 未完成                    | evidence-set relevance 仍可能混合 cross-encoder、RRF、element 和规则分数，不同数值空间会改变 route 间相对权重                                 | 每类 score 在同一 query/candidate pool 内校准或 rank-normalize；冻结集上 required evidence recall 不回退                     |
| BENCHMARK-PROJECTION-026 | P1     | 部分完成                  | 核心 identity、numeric 和常见视觉字段已保留，但任意扩展 metadata 还不是完全无损 round trip                                                    | 对声明的 benchmark evidence schema 做 property round trip；未知扩展字段有明确 namespaced 容器或明确拒绝策略                  |
| METRIC-LOCATOR-021       | P1     | 部分完成                  | candidate page coverage 已按 `(source_id, page)`；旧 `all_gold_pages_hit` 仍只比较 page number，报告中同时存在两种口径                        | 新增并采用 source-page paired headline；page-only 指标明确标记 legacy diagnostic，不用于发布门槛                             |
| VERIFY-TYPED-019         | P1     | 部分完成                  | numeric 冲突和 execution provenance 已增强；boolean proposition entailment、主体/关系/作用域和长文本 calibrated judge 仍未统一                | numeric 由 execution 验证；boolean 有正反命题结果；free-text 冻结人工集一致率 ≥90%；每个 supported claim 有 provenance       |
| QASPER-CONTRASTIVE-007   | P1     | 未实现                    | cross-page support slot 已拆分，但 QASPER boolean/contrastive 尚无 proposition、negation、condition、modal qualifier slots                    | 固定反例正确返回 `no`；unsupported yes/no 不增加；部署 route 不低于冻结基线                                                  |
| QASPER-LATENCY-008       | P1     | 未实现                    | generation、answerability、verification、finalization timing 尚未完整分段                                                                     | 分段 timing coverage 100%，给出 paired route-specific latency 和瓶颈                                                         |
| SEMANTIC-JUDGE-020       | P1     | 未验收                    | semantic F1 契约存在，但没有冻结 200 条人工校准 artifact                                                                                      | coverage ≥99.5%，人工一致率 ≥90%，数字/方向/单位冲突不得通过                                                                 |
| REPORT-HEADLINE-022      | P1     | 未实现                    | `qa_quality` 仍可同时包含 controller、CRAG 和 fixed route；相同 effective route 可能重复计权                                                  | headline 只统计实际部署 controller policy；fixed/CRAG/oracle 仅作 baseline 或 diagnostic                                     |
| RELEASE-GATE-027         | P1     | 未实现                    | contract correctness、paired regression、judge calibration、latency 和长期能力目标仍在同一 gate list                                          | 拆成三类 gate；contract 必须通过，paired regression 用置信区间，long-term target 不伪装成代码契约                            |
| IDENTITY-PROPERTY-023    | P2     | 未实现                    | identity 仍以固定回归样例为主，缺多表、多年份、alias、continuation 的随机组合验证                                                             | property-based round-trip/dedupe 测试中 identity collision 为 0                                                              |

## 6. 已关闭并从开放表移除的问题

以下问题已经有实现和包级回归证据，不再保留为开放 bug：

- dimension execution slot 被 `role == "operand"` 过滤；
- generic verifier 把 verified evidence 直接当成 cited evidence；
- quality retry 使用空查询；
- cross-page 只有单一 `support:cross_page`；
- hybrid item score 被父表 `evidence_id` 覆盖；
- reranker score 进入 first-stage RRF；
- learned ranker 不能形成真实 reranked stage；
- 相同文本跨 source 错误通过 reranker lineage；
- 相同 `plan_id` 的 planned/bound 状态没有 stage/version；
- stale embedded identity 被无条件信任；
- neighbor raw ID 无法命中 canonical identity；
- page ranking preview 被命名为 selected pages；
- RRF trace 声称执行了实际未应用的 modality top-k；
- benchmark index 遇到 `"5.0"` 或异常值直接抛错。

这些关闭结论只针对代码契约。它们是否改善真实数据集结果统一由
`CONTRACT-ARTIFACT-001` 验证，不把历史 artifact 当成本轮证据。

## 7. 下一步顺序

1. 先生成 FinanceBench 与 QASPER 各 2–5 条 smoke artifact，逐条检查
   `candidate → fused → reranked → selected → generation_context → verified_claim_support → emitted_citation`。
2. smoke 中 identity、slot、stage、citation 任一 contract violation 非 0，则停止
   并修首次断裂阶段，不调 reranker/MMR/prompt 掩盖问题。
3. smoke 通过后提交 QASPER 159×3 与 FinanceBench 20×4 聚焦验证。
4. 聚焦验证通过 contract gates 且部署 route 对冻结基线无显著回退后，才讨论全量
   benchmark。
5. `EVIDENCE-SET-BUDGET-024`、`SCORE-CALIBRATION-025`、
   `REPORT-HEADLINE-022` 和 `RELEASE-GATE-027` 在正式 Phase G 前必须关闭；不能通过
   修改评分权重或 gold 宣称达标。
