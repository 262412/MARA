# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-27

当前代码基线：`37517302acdf665296534a3163faea569ac2da82`

发布结论：**QASPER boolean 语义裁决和 Finance 结构化 operand 供给仍是 P0
阻塞项。QASPER v23 与 FinanceBench v21 均发生真实质量回退，当前不得重跑全量
benchmark。**

## 1. 文档范围与判断规则

本文只保留最新完成 artifact 中仍可复现的问题。问题必须同时具备：

1. artifact 或执行 trace 证据；
2. 可定位的代码路径和失效不变量；
3. 不依赖 gold 特判的修复方法；
4. 可自动验证的关闭标准。

旧 `avg_f1`、`avg_native_score` 和 `avg_mara_score` 保持原定义。新增诊断字段只能解释
阶段问题，不能被当作系统质量提升。局部样例改善不能关闭问题；修复必须在固定聚焦集
上不造成总体回退。

本次判断读取：

- QASPER v23，159 个样本 × 3 个 route，477/477 可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_root_invariants/qasper-typed-v23-root-invariants-l40s/01_core_text/20260727_024457_qasper-typed-v23-root-invariants-l40s-9953940`
- QASPER v22 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/qasper-typed-v22-verifier-budget-l40s/01_core_text/20260726_230904_qasper-typed-v22-verifier-budget-l40s-9952461`
- FinanceBench v21，20 个样本 × 4 个 route，80/80 可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_root_invariants/finance-v21-root-invariants-l40s/outputs/20260727_031107_finance-v21-root-invariants-l40s`
- FinanceBench v20 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/finance-v20-table-identity-segment-l40s/outputs/20260727_000149_finance-v20-table-identity-segment-l40s`

v23/v21 已写入非空 `index_contract`，因此证明新 artifact 的 provenance 记录已修复。
旧 v22/v20 的 `index_contract` 为空，所以本次版本差异仍只能作为同 manifest、样本和
模型配置下的行为对照，不能宣称是严格冻结索引的 paired A/B。

## 2. 最新结果

### 2.1 QASPER v23

| 指标                    |    v22 |    v23 |     变化 |
| ----------------------- | -----: | -----: | -------: |
| native/token F1         | 67.55% | 64.81% | -2.74 pp |
| semantic/typed exact    | 64.57% | 60.59% | -3.98 pp |
| citation recall         | 88.33% | 84.64% | -3.69 pp |
| 平均 generation latency | 2.67 s | 5.46 s |    +104% |

unanswerable 正确数保持不变，回退集中在 boolean。三条 route 的 boolean 正确数由
`50/99、51/99、51/99` 降为 `43/99、45/99、45/99`。逐预测比较只有 8 个改善，
却有 27 个退化。`insufficient_evidence` trace 从 51 增至 112，
`grounded_complete` 从 178 降至 85。

### 2.2 FinanceBench v21

| 指标                 |    v20 |    v21 |      变化 |
| -------------------- | -----: | -----: | --------: |
| overall native       |  8.75% |  3.75% |  -5.00 pp |
| quality-route native | 11.67% |  5.00% |  -6.67 pp |
| semantic F1          | 31.96% | 22.18% |  -9.78 pp |
| page hit             | 40.00% | 36.25% |  -3.75 pp |
| false abstention     | 17.50% | 25.00% |  +7.50 pp |
| slot coverage        | 70.71% | 55.05% | -15.66 pp |
| Candidate Recall     | 41.67% | 53.33% | +11.66 pp |
| Reranked Recall      | 25.83% | 31.67% |  +5.84 pp |

候选召回改善没有转化成 operand 覆盖。v21 最终 evidence 已出现 47 个 element 和
8 个 cell，但 60 条检索型 route 中只有 2 条启用结构扩展。计划成功执行数从 11
降到 4；4 个成功执行中 3 个答案正确，说明执行器在 operand 真正绑定后基本可靠，
主要故障仍位于索引、候选截断和 cell/slot 绑定层。

## 3. 根因分析

### 3.1 QASPER：高精度冲突保护被错误扩张成通用蕴含器

上一轮为了修复 `required` 与 `can/drop-in` 混淆，让所有
`yes_complete/no_complete` verdict 再经过
`boolean_quote_supports_relation()`。该函数是词干、anchor 和少量否定词组成的
启发式规则，不是完整语义蕴含器。

因此出现两类回退：

- 合法释义被拒绝，例如 “double annotated” 与 “labeled by two annotators”；
- 通用问题也受到只为 modal requirement 设计的 prompt 段落影响，原本稳定的
  complete verdict 大量变成 insufficient。

正确边界是：

- semantic judge 的 schema `complete/partial` 负责通用命题完整性；
- 确定性规则只否决可证明冲突的窄关系，例如
  `required/necessary/must` 与 `optional/without/drop-in`；
- 通用 grounded complete verdict 不再由词法 anchor 二次否决；
- modal 专用 prompt 只在问题确实询问 requirement 时加入。

### 3.2 Finance：显式 layout element 绕过了 table/cell 解析

`element_records_from_documents()` 当前只在文档没有 `element_id` 时调用
`parse_element_index_records()`。真实 PDF 文档通常已经带有 layout `element_id`，
于是直接走简单 `_element_record()`，不生成 `table_id/cell_id/row/column/value`。

这解释了 v21 的表面矛盾：索引中已经有 element，但绝大多数财务表仍没有可执行
cell identity。修复必须保留原 layout identity，同时让显式 table element 继续经过
financial table parser 并产生 atomic cell records。

### 3.3 Finance：top-20 截断发生在 required-slot 保护之前

element retriever 先按整句 token overlap 排序并截取 20 条，之后 QueryPlan 才做
required-slot 选择。年份和通用 finance 词很多的无关 cell 会占满 top-20，真正的
COGS、inventory、capex 等 cell 即使存在于完整 element index，也无法进入 bundle。

required-slot shortlist 必须前移到截断点：

1. 先对完整 element index 排序；
2. 用 QueryPlan 为每个 required slot 找到最高分结构候选；
3. 用这些候选替换未保护的通用 top-20 项；
4. trace 记录恢复数量，禁止静默扩大候选预算。

### 3.4 Finance：adapter 将候选数值写回已找到的 semantic cell

`finance_calculation_adapter` 在 expected-value cell 查找失败后，会按
metric/period 找 semantic cell；但 `_operand_from_cell()` 仍把上游候选数值写进
operand，而不是使用 cell 中的确定性值。结果是 cell 身份正确、value 仍错误，随后
被 verifier 拒绝。

cell 是数值事实来源。找到唯一 semantic cell 后，operand 的 value、period、scale、
currency 和 period kind 必须取自该 cell；上游候选数值只能用于查找，不得成为执行
输入。

### 3.5 Finance：page 与 atomic narrative 没有清晰边界

当前 verifier 只在 page 包含多行多数字时要求 atomic binding。单行 page chunk 即使
没有 cell/element identity 仍可执行；相反，PepsiCo credit agreement 这类合法的
叙述型数值事实没有 table cell，只能绑定整页。

修复边界：

- 所有 `evidence_level=page` 的 operand 均不得直接执行；
- table operand 必须绑定 cell；
- 叙述型财务事实按句子生成稳定 atomic span element，每个 span 只包含一个带币种或
  scale 的金额，并记录 metric、period、value 和 source backref；
- 重复数值必须绑定不同 span identity，不能用同一整页 evidence ID 充当两个 operand。

### 3.6 Finance segment：实体绑定后仍缺少指标区段绑定

`finance_segment_comparison` 会解析整个 page/table，再以 entity+period 写入字典。
同一页面先出现 `Net revenue`、后出现 `Operating income` 时，后者覆盖前者。其他
geography 或 cost table 也会混入矩阵。因此 v21 的 Data Center 使用了
`1848/991` operating income，而不是 `6043/3694` net revenue，并最终选择
Acquisition-related Costs。

segment 比较必须先锁定问题要求的 `Net revenue/Net sales` 区段，只解析该区段到
`Total net revenue` 或下一指标标题为止，再建立 entity-period matrix。

### 3.7 Finance period：year 相同不代表期间相同

`01928` 同页同时有 Three Months Ended 和 Twelve Months Ended。当前直接数值路径
尚不支持 adjusted EBITDA，且 CalculationOperand/FinancialTableCell 没有完整传播
`period_kind`，最终取到季度 540 而不是全年 2018。

修复必须：

- 将 adjusted EBITDA 纳入确定性 direct-value adapter；
- `FinancialTableCell → CalculationOperand → verifier` 全链路传播
  `period_kind`；
- FY/full-year 问题只允许 fiscal-year cell，quarter cell 不得作为 fallback。

### 3.8 Reranker trace 仍不是真实执行证明

artifact 中 text evidence 可见上游 `reranking_score`，但 bundle 的
`ranking_trace.backend_execution` 仍全部为 `not_recorded`，同时
`reranked_evidence` 实际只是 post-fusion 前 30 条投影。当前不能声称本层执行了 BGE
reranker，也不能区分“上游已重排”和“完全未重排”。

本问题不允许通过伪造 backend/model 名称关闭。只有在 trace 能从真实运行对象或上游
score lineage 得到执行阶段、score field、scored count 和未评分候选数后才能关闭。

## 4. 开放问题表

| ID                             | 优先级 | 状态       | 本轮修复                                                                                         | 关闭标准                                                                                          |
| ------------------------------ | ------ | ---------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| QASPER-SEMANTIC-GATE-006       | P0     | 开放       | 通用 complete verdict 信任 schema 语义；确定性规则只处理高精度 modal 冲突；modal prompt 条件启用 | 159×3 可用且 boolean exact 不低于 v22；`b065` 保持正确；无新增大范围 insufficient；延迟回到预算内 |
| FIN-INDEX-PARSE-BYPASS-007     | P0     | 开放       | 显式 layout element 继续经过 financial parser，保留原 identity 并生成 cell records               | 新索引的 table/cell coverage 显著非零；显式 element table 单测产生稳定 cell identity              |
| FIN-SLOT-PRECAP-008            | P0     | 开放       | required-slot 保护前移到 element top-20 截断之前                                                 | 每个可用 required slot 的最佳候选进入 top-20；trace 记录恢复数；预算不扩大                        |
| FIN-CELL-VALUE-009             | P0     | 开放       | semantic cell 的确定性值覆盖未绑定候选值                                                         | 计划中 value 与指定 cell 完全一致；`04854` 使用 3676.2 与 460.8                                   |
| FIN-ATOMIC-NARRATIVE-010       | P0     | 开放       | page 一律禁止直接执行；叙述金额生成稳定 atomic span                                              | 所有成功 operand 为 cell 或 atomic span；`00882` 两个 4.2B 绑定两个不同 identity                  |
| FIN-SEGMENT-METRIC-003         | P1     | 开放       | segment matrix 增加 metric-section 边界                                                          | `00563` 只含 segment net revenue，返回 Data Center                                                |
| FIN-PERIOD-GRANULARITY-002     | P1     | 开放       | adjusted EBITDA direct adapter 与 period-kind 全链传播                                           | `01928` 绑定 FY2023 2018m，不绑定 quarter 540                                                     |
| RERANK-TRACE-001               | P1     | 开放       | 记录真实上游 score lineage 或真实本层执行，不再用 `not_recorded` 掩盖                            | trace 能区分 upstream reranked、local rerank 和 no rerank；禁止把 shortlist 当 rerank             |
| BENCH-ROUTE-INTERPRETATION-004 | P1     | 开放       | 保留 route agreement，发布结论按部署 route 而非重复 route 平均解释                               | 报告明确 headline route；相同输出不作为独立增益                                                   |
| RELEASE-001                    | P1     | 被 P0 阻塞 | 完成本轮本地门槛后只提交 QASPER/Finance 聚焦任务                                                 | 所有 P0 经真实 artifact 关闭后才允许全量重跑                                                      |

## 5. 已关闭并从开放表移除

- **BENCH-PAIRED-002（新 artifact provenance）：** v23/v21 的
  `index_contract` 已非空；旧 artifact 无 digest 的历史限制仍在，但新运行不再缺失。
- **BENCH-TYPED-METRIC-004：** v23 已完整报告 QASPER typed accuracy，互斥 typed
  answer 不再由 token overlap 掩盖。
- **EVAL-LOCATOR-002：** v21 已分别报告 strict page hit 21.25% 和
  equivalent-evidence page hit 36.25%。
- **最终答案重复：** 最新聚焦 artifact 中 final-answer duplicate rate 已为 0；
  route 间相同输出属于解释问题，不再混入文本去重问题。
- **计算执行器缺失：** 执行器存在且成功执行时 3/4 数值正确；当前问题明确归属于
  operand identity/value binding，而不是继续记录为“没有执行器”。

## 6. 实施顺序与保护测试

必须按以下顺序完成：

1. 先加入 QASPER semantic paraphrase、显式 element table、atomic narrative span、
   pre-cap slot restore、mixed-pool structure coverage、page atomic guard、segment
   metric section、period kind 和 cell-value source-of-truth 测试；
2. 在生产代码未修改时确认上述测试失败；
3. 单独提交保护测试和本文档；
4. 实现索引/选择/binding 修复；
5. 运行聚焦测试、完整 `benchmark/tests`、完整 `libs/ktem/ktem_tests`、hygiene 和
   changed-files pre-commit；
6. 提交实现；
7. 提交 QASPER 159×3 与 FinanceBench 20×4 聚焦 Slurm 任务，不监听至完成。

本轮生产代码修改前，新增保护测试结果为 **9 failed、73 passed**。失败分别对应开放表
中的真实断层，不包含人为构造的 gold 特判。

## 7. 本地与 artifact 验收

本地门槛：

- 新保护测试全部通过；
- 相关 benchmark 与 DocQA 聚焦测试通过；
- 完整 `benchmark/tests` 与 `libs/ktem/ktem_tests` 通过；
- codebase hygiene 通过且不刷新 baseline；
- changed-files pre-commit 通过；
- `MARA`/`MARA-cli` 公开命令、参数和持久化字段不变；
- 仓库根目录不产生 `data/`、`datasets/`、`outputs/`。

QASPER artifact 门槛：

- 477/477 可用，execution error=0；
- boolean exact 不低于 v22；
- modal 反例修复保留，同时 win/loss 不再呈现大范围净回退；
- generation latency 中位数相对 v22 增幅不超过 20%。

FinanceBench artifact 门槛：

- 80/80 可用，index contract 非空；
- table/cell/atomic-span identity 与 structure expansion 明显进入正式 route；
- 所有成功执行 operand 均可追溯到 cell 或 atomic span；
- execution success 不得通过放松 page 验证获得；
- 重点检查 `04854`、`00882`、`10285`、`03531`、`03031`、`00563`、
  `01928`、`10499`；
- native、semantic F1 和 false abstention 至少不低于 v20；否则继续停留在聚焦验证，
  禁止全量重跑。

若结构索引仍无法给 required slot 提供原子身份，下一轮必须继续修 index/IR，不得通过
prompt、阈值、expected gold value 或放宽 verifier 制造分数提升。
