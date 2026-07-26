# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-26
对应代码：`ec5d5865`
状态结论：**仍有 P0 阻塞项，暂不应重跑全量 benchmark。**

## 1. 本文档的边界

本文档只记录最新完成的聚焦验证仍能复现、并且有 artifact 或代码路径支撑的问题。已经解决、已被新证据否定、或仅来自旧运行推测的问题从开放表移除，保留在“已关闭问题”中作为简短审计记录。

本轮分析使用以下完成且无 execution error/timeout 的运行：

- QASPER v18，159/159：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-qasper-typed-v18-proposition-provenance-l40s/01_core_text/20260726_134856_residual-qasper-typed-v18-proposition-provenance-l40s-9944162`
- FinanceBench v17，20 × 4 = 80/80：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-finance-v17-semantic-scale-provenance-l40s/outputs/20260726_145113_residual-finance-v17-semantic-scale-provenance-l40s`

对照运行分别为 QASPER v17 和 FinanceBench v16。旧运行缺少部分 provenance，因此涉及新旧因果归因时只报告为“观测差异”，不伪装成严格受控实验。

## 2. 最新事实基线

### 2.1 QASPER

| 指标 | v17 | v18 | 结论 |
|---|---:|---:|---|
| token/native F1 | 62.02% | 61.93% | -0.09 pp |
| semantic F1 | 58.49% | 58.49% | 无提升 |
| evidence F1 | 19.35% | 19.35% | 无提升 |
| 结构合法率 | — | 97.48%（155/159） | 未达 100% |
| boolean exact | 45/99 | 45/99 | 无提升 |
| unanswerable exact | 48/60 | 48/60 | 无提升 |

QASPER v9 判定器确实覆盖了全部 99 条 boolean 样本，因此“判定分支未执行”已关闭。但执行并不等于有效：

- 85 条判为 `insufficient_evidence`，10 条 `yes`，4 条 `no`。
- 20 条旧 boolean abstention 中，19 条仍 abstain；唯一恢复为 `yes` 的样本 gold 为 `no`。
- 20 条中有 12 条的 gold evidence 已在最终上下文；其中 10 条仍被原始回答判为 insufficient。
- 4 条 gold unanswerable 被输出为 free text，造成结构契约失败。

### 2.2 FinanceBench

| 指标 | v16 | v17 | 结论 |
|---|---:|---:|---|
| token F1 | 12.17% | 14.07% | +1.90 pp |
| native numeric | 10.00% | 11.25% | +1.25 pp，仍远低于 20% 门槛 |
| semantic F1 | 25.08% | 33.75% | +8.67 pp |
| page hit | 33.75% | 45.00% | +11.25 pp，仍低于 70% 门槛 |
| false abstention | 23.75% | 16.25% | 改善，但仍高于 15% 门槛 |
| Candidate Recall@50 | 34.17% | 45.83% | 改善，仍有明显召回缺口 |
| Reranked Recall@10 | 27.50% | 37.50% | 改善，仍有排序丢失 |
| all-gold-pages hit | 18.75% | 27.50% | 仍低于 35% 门槛 |
| all-operands / execution | 20.83% | 37.50% | 仍低于 50% 门槛 |
| cell accuracy | 79.41% | 100% | 本次样本已达标 |
| unit accuracy | 50.00% | 83.33% | 改善，仍低于 98% 门槛 |
| lineage consistency | 100% | 98.86% | 出现新的候选血缘违例 |

24 条适用计算问题中，9 条成功执行且 verifier 通过，15 条仍未形成可执行计划；成功执行的 9 条中有 6 条 native 与 semantic 均正确。

已证实的正向变化：

- `04854` 正确绑定 General Mills 的 operating cash flow 3676.2 与 capital expenditure 460.8，得到 3215.4 million，证明跨证据边界和表格 scale 修复有效。
- `03031` 新增正确结果 5818。
- `03531`、`10285` 等问题不再用错误年份或错误资产项强行计算，说明 verifier 的拒绝是有价值的。

仍需解释的退化和错误：

- `00882`：同一运行中 QueryPlan slot 记录 page 85 的 evidence ID，但计算器从最终已选上下文中的 page 2 证据绑定两个 4.2B 操作数；语义、数值和页面证据均成立，却因 exact evidence ID 不一致被判 `required_slot_missing`，从旧版正确 `$8.4B` 退化为 abstain。
- `04980`：证据明确为 4,625 million，程序正确得到 4.625B，但 gold 为 `$4.60`，历史 native 的 0.1% 数值容差将其判错。这是评测精度/舍入契约问题，不是计算错误。
- `04302`：候选阶段有相关证据，但 rerank 后丢失。
- `10499`：错误绑定到 COGS 7.0 或 pension distractor，属于表格 metric 语义绑定不足。
- `03531`、`10285`：仍属于召回失败。

## 3. 开放问题表

| ID | 优先级 | 状态 | 根因 | 当前影响 | 关闭标准 |
|---|---|---|---|---|---|
| QASPER-PROP-002 | P0 | 开放 | boolean verifier 用词形/动词重叠近似命题蕴含，无法区分“相关主题”与“完整回答” | boolean exact 无提升；存在 false reject 与 false accept | 冻结样本中完整命题被接受、部分命题被拒绝；结构合法率 100%，boolean semantic F1 明显提升且不损害 unanswerable |
| FIN-IDENTITY-002 | P0 | 开放 | 初轮 slot 的 exact evidence ID 被错误当成最终 operand 授权集合；跨页/重建后的同义证据身份不能统一 | `00882` 等已具备正确证据的问题错误 abstain | 最终 selected evidence 中 metric/period/value/unit/cell 语义一致的 operand 可通过；错 metric/period 仍必须失败 |
| FIN-RETRIEVAL-001 | P0 | 开放 | page/table 召回和重排仍不足，候选召回与 rerank recall 均未达到发布门槛 | 15/24 计算问题无法执行，page hit 45% | page hit ≥70%，all-gold-pages ≥35%，all-operands ≥50%，并通过固定样本回归 |
| FIN-TABLE-SEM-002 | P0 | 开放 | 表格行列标签、metric 别名与 entity/period 绑定仍不完整 | `10499` 等绑定 distractor；operand accuracy 56.86% | 冻结 distractor 用例选择正确行/列；operand accuracy 恢复并达到门槛 |
| RERANK-LINEAGE-002 | P1 | 开放 | `candidate_evidence` 在 hybrid fusion 前截取，而后续 fusion 可把原 top-80 之外证据提升到 reranked 输出 | 6 个 reranked identity 不在声明的 candidate pool | candidate pool 精确等于 post-fusion reranker 输入；reranked IDs 必须是其子集，违例为 0 |
| RERANK-TRACE-001 | P1 | 开放 | trace 只有排序结果，不能证明实际执行了哪个 reranker backend | 无法区分 BGE 执行、上游分数复用或 fallback | trace 明确记录 backend、模型、输入/输出数和执行状态；未执行时不得标记为 BGE |
| REPRO-001 | P1 | 开放 | multimodal Slurm 未导出 text/retrieval endpoint；provenance 未采集 colvision endpoint | Finance artifact 不能完整重建 8000/8002/8003 服务拓扑 | artifact 记录 text、VLM、retrieval、colvision endpoint/model 与配置 hash |
| FIN-EVAL-001 | P1 | 开放 | 历史 native numeric 只有固定相对容差，没有数据集精度/舍入语义 | `04980` 的正确 4.625B 被历史指标判错 | 保留历史 native 不变；新增独立 precision-aware diagnostic，并明确报告两者差异 |
| FIN-UNIT-002 | P1 | 开放 | scale/currency/unit 绑定虽已改善，但覆盖不足 | unit accuracy 83.33%，低于 98% | 固定 scale/currency 回归全部通过，聚焦运行 unit accuracy ≥98% |
| RELEASE-001 | P1 | 外部阻塞 | QASPER 与 FinanceBench 的 P0 指标未过门槛 | 全量重跑会放大成本而不能证明修复完成 | 所有 P0 聚焦验证通过后才能提交一次正式全量重跑 |

## 4. 根因反思

前几轮没有从根本解决问题，主要不是“阈值还没调准”，而是三个层次被混在了一起：

1. **把执行覆盖当成语义正确。** QASPER v9 从未执行变成 99/99 执行，只解决控制流；其内部仍用关键词和词形重叠判断完整命题，所以指标没有提升。
2. **把临时检索身份当成事实身份。** Finance 的 slot 在初轮检索时绑定一个 chunk ID，后续 page expansion、canonicalization 或 evidence selection 可能产生另一个 ID。verifier 对 exact ID 做授权，导致“事实相同但对象 ID 不同”的正确证据被拒绝。
3. **trace 描述的阶段与真实执行阶段不一致。** 候选池在 fusion 前记录，reranked 输出在 fusion 后产生，因此报告可以出现逻辑上不可能的“输出不属于输入”。这同时削弱了此前因果分析的可信度。

因此，核心修复不能继续围绕单个样本增加字符串例外，而必须建立三条不变量：

- **命题不变量：** boolean 的判定对象是 subject、relation、object、scope、polarity 构成的完整命题；主题相关或部分支持不得等价为 yes/no。
- **证据绑定不变量：** exact evidence ID 只用于 lineage；计算授权依据必须是最终 selected evidence 上可复核的 cell/value/metric/period/unit/entity 绑定。
- **评测与 trace 不变量：** 每个输出必须属于声明的实际输入集合；历史指标保持原定义，新的诊断指标必须独立命名；未记录的 backend 不得被推断为已执行。

## 5. 本轮落实方案

### 5.1 QASPER 命题级 answerability v10

- 将模型判定扩展为 `yes_complete`、`no_complete`、`yes_partial`、`no_partial`、`insufficient_evidence`。
- 只有 grounded 且 complete 的同一命题才能映射为最终 `yes/no`；partial 一律保留为 insufficient。
- prompt 明确定义 process/outcome、mention/perform、experimental control/quality validation 等边界，并允许引用完整但受限长度的连续证据。
- exact quote 只负责 grounding，不再用动词重叠代替 relation entailment。
- 新增两个保护样本：
  - “系统控制实验数据”不能推出“验证质量”，必须判 partial。
  - “不是 silver bullet”若直接回答是否存在 downside，应判 complete。

### 5.2 Finance 统一身份与语义绑定

- 移除“operand evidence ID 必须属于初轮 slot evidence IDs”的错误授权条件。
- 仍要求 operand 来自最终 selected evidence，并逐项验证 evidence/cell、metric、period、value、unit、scale、currency 和 entity。
- slot ID membership 保留为诊断字段，不能覆盖上述语义验证。
- 新增 `00882` 型回归：初轮 slot 与最终正确证据 ID 不同仍应通过；错 period/metric 必须继续失败。

### 5.3 Rerank 血缘与可复现性

- canonicalize 和 hybrid fusion 后，再截取真实 top-80 作为 reranker input。
- `candidate_evidence` 必须记录该真实输入；`reranked_evidence` 必须为其子集。
- trace 记录 candidate stage、limit、input/output count 和已知 backend 状态；没有执行证据时明确标记 `not_recorded`。
- multimodal Slurm 显式导出 text LLM、retrieval 和统一 LLM endpoint；provenance 增加 colvision endpoint。

### 5.4 评测纪律

- 不修改 `avg_f1`、native numeric 或既有容差。
- `04980` 只作为 precision-aware diagnostic 的设计依据，不能通过读取 gold 决定输出舍入。
- 修复后先重跑 QASPER 159 条和 FinanceBench 20 × 4；只有 P0 关闭才允许全量 benchmark。

## 6. 实施与验证清单

执行顺序固定为：

1. 先提交 characterization/regression tests。
2. 实现 QASPER v10、Finance semantic binding、post-fusion candidate lineage 和 provenance。
3. 运行相关 benchmark/ktem 单元测试、changed-files pre-commit 和代码卫生检查。
4. 提交新的 QASPER 159 与 FinanceBench 20 × 4 聚焦验证。
5. 用新 artifact 更新本表；不得用本地 mock 通过代替真实聚焦指标。

在新的聚焦 artifact 完成前，本轮代码修复只能标记为“已实现/待运行验证”，不能提前把 P0 标记为已关闭。

## 7. 已关闭问题

以下问题已由最新 artifact 直接证明关闭，不再保留在开放表：

- **QASPER 判定分支未执行：** v18 中 99/99 boolean 样本已运行 v9 判定器。
- **Finance 跨证据边界无法计算：** `04854` 已正确跨证据绑定并计算 3215.4 million。
- **Finance `04980` 的 billion scale 误读：** 当前程序正确绑定 4,625 million 并得到 4.625B；剩余错误属于独立的评测精度契约。
- **Finance cell 定位错误作为全局阻塞：** 本次聚焦运行 cell accuracy 为 100%；仍存在的错误已归入 metric/period/entity 语义绑定，而不是继续重复记录为 cell 定位问题。

这些关闭结论只针对上述问题定义；不代表 FinanceBench 整体检索、单位和数值准确率已经达标。
