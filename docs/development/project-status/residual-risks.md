# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-28

## 1. 当前结论

本轮已按完整审查报告执行基础契约修复。代码建立在
`aa50867cf1bfcde3905948a1c279449b503fe037` 之上，本轮实现与本文档由同一 Git
提交记录；没有提交新的 Slurm 任务。

当前结论分为两层：

- **代码不变量层：已通过。** Evidence Identity、runtime→benchmark 无损投影、
  单一 QueryPlan、阶段语义、claim/citation provenance 和阶段覆盖指标已有唯一实现，
  完整 `ktem` 与 `benchmark` 测试通过。
- **数据集能力层：尚未验收。** 当前没有使用本轮代码生成新的 QASPER 或
  FinanceBench artifact，因此不能声称 native、semantic F1、boolean exact、cell
  recall 或 numeric accuracy 已恢复。

发布结论：**暂不运行全量 benchmark。先运行 QASPER 159×3 和 FinanceBench 20×4
聚焦验证；只有基础契约在真实 artifact 中成立且部署 route 不回退，才允许全量重跑。**

旧文档中关于任务 `9976017` 正在等待的描述已经过期，已删除。本文不把历史 Slurm
状态当作当前事实。

## 2. 事实来源

本轮依据：

- 用户提供的完整静态审查报告：
  `/mnt/fastscratch/users/tbczhang/.codex/attachments/d2be4168-b94f-40ad-abb6-721a68ded849/pasted-text.txt`
- QASPER v24，159×3：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_evidence_invariants/qasper-typed-v24-evidence-invariants-l40s/01_core_text/20260727_134621_qasper-typed-v24-evidence-invariants-l40s-9962978`
- QASPER v22 行为基线：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/qasper-typed-v22-verifier-budget-l40s/01_core_text/20260726_230904_qasper-typed-v22-verifier-budget-l40s-9952461`
- FinanceBench v22，20×4：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_evidence_invariants/finance-v22-evidence-invariants-l40s/outputs/20260727_195210_finance-v22-evidence-invariants-l40s`
- FinanceBench v20 行为基线：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/finance-v20-table-identity-segment-l40s/outputs/20260727_000149_finance-v20-table-identity-segment-l40s`

历史 artifact 仍用于描述修复前问题，不能用于证明本轮代码已经关闭这些问题。

## 3. 为什么过去多轮修改没有根治

过去的问题不是一组互不相关的 prompt、阈值或数据集特例，而是五个系统契约没有
闭合：

1. **Identity Contract 缺失。** 同一个 cell 在不同阶段分别使用 `cell_id`、
   parent `evidence_id`、`element_id`、table ID 或 row/column；跨模块 join 会静默
   丢失。
2. **Plan Contract 缺失。** controller、retrieval、selection 和 verifier 会各自
   重新解释问题，没有共享唯一 `plan_id`、slot 集合和 required 语义。
3. **Stage Contract 缺失。** candidate、fused、reranked、selected、used、
   verified、cited 混用，字段名称和实际内容不一致。
4. **Verification Contract 缺失。** “evidence 曾经出现”被误认为“evidence 支持
   claim”；两 token 重叠会误放行错误数字或方向。
5. **Metric Contract 缺失。** page、element、cell、span 和 slot 的 gold identity
   粒度不一致，page hit 上升可能同时伴随 operand coverage 下降。

本轮完整回归还发现了一个直接实例：element score 已按 canonical identity 建表，
后续却使用 raw selected ID 过滤，导致 score map 被清空。单测每个模块都可能正常，
但端到端 identity join 已经断裂。这解释了过去“一项上升、另一项回退”的反复。

## 4. 本轮已落实的基础契约

### 4.1 Evidence Identity 与去重

- 新增不可变 `EvidenceIdentity(source_id, kind, local_id)`；统一身份优先级为
  cell → span → table row/column → element → bbox → chunk/evidence → text。
- parser、dedupe、RRF、selection、calculation、citation 和 benchmark projection
  使用同一个 `identity_of()`，不再自行猜测主键。
- 相同父表的两个 cell 保持不同 identity；相同文本不跨 source 合并。
- exact text、overlap、MinHash 和 semantic 去重都执行结构化事实冲突检查。
- 合并重复项时保留代表正文，并 union alias、source backref、retriever lineage 和
  duplicate IDs；冲突事实不合并。

### 4.2 无损 runtime→benchmark 投影

- 新增共享 `BenchmarkEvidenceRecord`，`index_metadata` 不再维护独立字段白名单。
- identity、source/page alias、cell/table、period、unit、scale、currency、
  continuation、chunk、hash、retrieval lineage 和 source backref 可 round trip。
- source canonicalization 会同步重建 identity/canonical ID，同时保留
  `runtime_source_id` 和 source alias。
- benchmark element projection 优先使用 atomic cell/span，而不是父 element。

### 4.3 单一 QueryPlan

- 每个 request 只生成一次确定性 `plan_id`，controller、retrieval、selection、
  calculation 和 verifier 复用同一对象。
- `EvidenceSlot` 明确区分 `required_for_retrieval`、
  `required_for_execution`、`required_for_verification`。
- slot 绑定保存 canonical evidence identity。
- 第二轮检索按 missing slot 独立执行，记录 `round_id/query_id/slot_id`；二轮后
  required retrieval slot 仍缺失时阻止生成。
- 普通 “from” 不再误触发跨页计划；无运算意图的直接 numeric 问题只创建一个
  operand。

### 4.4 真实阶段与 evidence-set selection

- 明确记录 candidate、fused、reranked、selected、used、verified、cited。
- 未执行真实 reranker 时，`reranked` 指标为 unavailable，不再用 shortlist 冒充。
- dense/sparse 等 retriever list 先 canonicalize，再做真正 RRF；同一 retriever
  内重复 identity 不重复计权。
- page-first 只产生 page rank，不再前置删除三页以外候选；page score 使用 max 与
  top-3 mean，避免奖励碎片数量。
- 最终选择按 relevance、slot new coverage、structure、contrast、redundancy 和
  cost 的边际收益构造 evidence set；required slot evidence 不被普通 MMR 删除。
- continuation、parent 和 neighbor expansion 按可用 edge 启用，不再由全局 80%
  metadata coverage 一票否决。

### 4.5 Calculation、claim verification 与 citation

- CalculationOperand 同时保留 legacy raw ID 和 canonical
  `evidence_identity/scale_evidence_identity`。
- 合成 cell identity 可回溯父表；value、period、unit、scale、currency 和 slot
  一致性仍由确定性 verifier 检查。
- execution citation 优先使用实际 operand/dimension identity；benchmark
  finalizer 把这些 evidence 记录为 used/cited，不再从候选首项猜 citation。
- verifier 返回 `VerifiedClaim`，状态为 supported/contradicted/unknown，并分别
  记录支持与冲突 evidence identity。
- 删除“两 token 重叠即可支持”的最终判定；错误数字、年份和方向冲突优先判为
  contradicted。证据不足但未达到反证置信度时返回 unknown，不伪造 citation。
- evidence-only 和 empty-answer 路径也使用 canonical identity。

### 4.6 Benchmark metric contract

- `avg_f1` 继续是历史 token F1，不重定义；dataset native 仍是正式数据集指标。
- semantic claim F1 保持补充指标，适合“答案包含 gold 且语义、方向、数字和单位
  正确”的评价，但不能重命名成旧 F1，也不能把新指标绝对值抬升算成系统提升。
- candidate evidence coverage 与 candidate page coverage 分开；gold cell/span
  存在时不再由同页错误 element 计为 evidence 命中。
- 新增 selected、used、verified、cited evidence coverage。
- 支持 `gold_evidence_requirements` 及多个 acceptable evidence，区分 strict gold
  page 与等价正确证据。
- calculation accuracy 被限制在 `[0,1]`。

## 5. 本地验证证据

| 验证                     | 结果                                                         |
| ------------------------ | ------------------------------------------------------------ |
| 契约定向回归             | 170 passed                                                   |
| `libs/ktem/ktem_tests`   | 1378 passed，45 warnings                                     |
| `benchmark/tests`        | 476 passed，6 warnings                                       |
| codebase hygiene         | 无 ratchet violation；未刷新 baseline                        |
| changed-files pre-commit | black、isort、flake8、autoflake、mypy、codespell 全通过      |
| 公共命令面               | 未修改 `MARA`、`MARA-cli`、`MARA docqa` 命令或参数           |
| 存储预检                 | `.venv` 位于 fastscratch；无 repo-root data/datasets/outputs |
| fastscratch quota        | 140.8G/500G，447952/500000 files；本轮未下载模型或建索引     |

测试通过证明代码不变量成立，不等于真实 benchmark 指标达标。

## 6. 最新开放问题表

| ID                     | 优先级 | 状态                      | 真实未完成内容                                                                                                                                                                                        | 关闭标准                                                                                                                                      |
| ---------------------- | ------ | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| CONTRACT-ARTIFACT-001  | P0     | 待聚焦验证                | 本轮基础契约尚无新 QASPER/Finance artifact                                                                                                                                                            | QASPER 159×3、Finance 20×4 完整结束；identity round trip、stage lineage、used=cited provenance coverage 100%；部署 route 对冻结基线无显著回退 |
| QASPER-CONTRASTIVE-007 | P1     | 未实现                    | boolean/contrastive plan 尚无 proposition support、contradiction、condition、modal qualifier 独立 slots；发现冲突后仍不能定向恢复缺失极性                                                             | 固定反例 `b06512c17d99f9339ffdab12cedbc63501ff527e` 返回 `no`；部署 route boolean 不低于 v22；unsupported yes/no 不增加                       |
| QASPER-LATENCY-008     | P1     | 未实现                    | generation、answerability judge、finalization 未完整分段，无法定位 v22→v24 的 2.19s→5.45s 回退                                                                                                        | 分段 timing coverage 100%；给出 route-specific paired latency 与瓶颈归因                                                                      |
| FIN-ATOMIC-SUPPLY-011  | P0     | 代码已有，artifact 未证实 | wrapped/value-first table、soft-wrapped narrative 和局部单位/期间解析已实现，但真实 PDF 多样性下能否稳定供给 atomic cell/span 尚未由本轮 artifact 证明                                                | `10285/04854/10499/00882/01928/04980/03031` 固定样例全部满足 cell/span、period、scale、execution citation 不变量；缺证据时不执行              |
| VERIFY-TYPED-019       | P1     | 部分完成                  | exact numeric/year/direction 与 claim-specific identity 已实现；boolean proposition entailment、长文本 calibrated NLI/LLM judge、跨多个 operand 的 claim→execution provenance 仍需统一 typed verifier | numeric 由 CalculationExecution 验证；boolean 有正反命题结果；free-text 在冻结人工集一致率 ≥90%；每个 supported claim 有可审计 provenance     |
| SEMANTIC-JUDGE-020     | P1     | 未验收                    | semantic F1 设计合理，但本地 judge 尚无冻结 200 条人工校准结果                                                                                                                                        | coverage ≥99.5%，与人工标签一致率 ≥90%，冲突数字/方向/单位不得通过                                                                            |
| METRIC-GRAIN-021       | P1     | 部分完成                  | 已有 stage evidence coverage，但 source-page、table、cell/span、slot 尚未在每个阶段分别报告；数据集 converter 也未普遍产出 GoldRequirement                                                            | candidate/reranked/selected/used/verified/cited 均报告所需粒度；多页/多表样例能定位首次丢失阶段                                               |
| REPORT-HEADLINE-022    | P1     | 未实现                    | controller 与 CRAG 可能执行相同 effective route，当前报告仍可能把 route matrix 重复计入“系统总分”                                                                                                     | headline 只使用实际部署 controller policy；fixed routes 仅作为 baseline/diagnostic                                                            |
| IDENTITY-PROPERTY-023  | P2     | 未实现                    | 当前保护测试是固定样例，尚无随机多表、多年份、alias、continuation collision 测试                                                                                                                      | property-based round-trip/dedupe 测试覆盖上述组合，identity collision 为 0                                                                    |

## 7. 已从开放表移除的事项

以下问题已有代码不变量和包级回归证明，不再作为独立开放 bug；它们仍需通过
`CONTRACT-ARTIFACT-001` 验证真实效果：

- raw/canonical ID 混用导致 element score 静默清空；
- exact-text 去重绕过结构化事实冲突检查；
- 相同父表 cell 被合并；
- runtime→benchmark 字段白名单丢失 period/unit/lineage；
- controller/retrieval/selection 重建不同 QueryPlan；
- 二轮多个 slot 拼成单一 query；
- page-first 前置三页硬裁剪；
- shortlist 冒充 reranker；
- 全局 structure coverage gate 禁用已有 continuation edge；
- 两 token overlap 直接判 claim supported；
- execution citation 从候选首项漂移；
- cell/operator accuracy 产生负值；
- evidence-only citation 继续使用 raw evidence ID。

旧的 `FIN-WRAPPED-TABLE-CELL-011` 到 `FIN-CITATION-BACKREF-015` 已合并为
`FIN-ATOMIC-SUPPLY-011`，因为它们目前共享同一剩余事实：代码路径存在，但尚无本轮
真实 artifact。继续把它们写成多个“已实现待验证”不会增加诊断信息。

## 8. 下一步与验收分层

下一步只运行两组聚焦验证，不提交全量：

1. QASPER 159×3：重点检查 boolean exact、false abstention、stage coverage 和分段
   latency。
2. FinanceBench 20×4：重点检查 all-operands、atomic cell/span、period/unit、
   deterministic execution、used/verified/cited provenance。

验收按三类分开：

- **Contract correctness：必须 100%。** identity round trip、阶段字段真实性、
  calculation provenance、citation provenance、指标范围、JSON validity。
- **Paired regression：用 paired 差异和置信区间。** 部署 route native/semantic、
  false abstention 和 latency；不要求每个诊断 route 的离散正确数完全相同。
- **Long-term capability：不是单个基础契约补丁的伪通过条件。** Finance native
  20%、QASPER semantic 80% 等仍可作为正式发布目标，但不能通过调评分权重或修改
  gold 宣称本轮已达标。

聚焦 artifact 未通过时，应报告首次失败阶段并只修该契约。禁止重新调 MMR 权重、
CRAG threshold、prompt 或 Finance 特例来掩盖 identity、slot、stage 或 provenance
断层。
