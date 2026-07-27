# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-27

最新 artifact 基线代码：`7077e9af63f77a9ec0b37a320d5a518021e1c558`

本轮保护测试提交：`c47596f`

本轮实现提交：`6965bb6`

发布结论：**仍有 P0 结构绑定、QASPER 关系校验和评测可比性阻塞；本轮只能提交
聚焦验证，不能直接重跑全量 benchmark。**

## 1. 文档边界与判断原则

本文只保留以下内容：

1. 最新完成 artifact 中仍能复现的问题；
2. 能由 artifact 与当前执行路径共同证明的根因；
3. 对应的修复、不变量、保护测试和关闭标准。

已经由最新 artifact 关闭的问题从开放表移除。分数下降、prompt 不够长、top-k
不够大或模型不够强不是根因；只有定位到任务契约、证据身份、语义绑定、执行验证或
评测口径的具体失效点，才记录为根因。旧指标保持原定义，新增诊断不得伪装成历史
指标提升。

本轮读取的最新 artifact：

- QASPER v22，159 个样本 × 3 个正式 route，共 477/477 条可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/qasper-typed-v22-verifier-budget-l40s/01_core_text/20260726_230904_qasper-typed-v22-verifier-budget-l40s-9952461`
- QASPER v20 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/qasper-typed-v20-invariant-guard-l40s/01_core_text/20260726_200412_qasper-typed-v20-invariant-guard-l40s-9949298`
- FinanceBench v20，20 个样本 × 4 个正式 route，共 80/80 条可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/finance-v20-table-identity-segment-l40s/outputs/20260727_000149_finance-v20-table-identity-segment-l40s`
- FinanceBench v19 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/finance-v19-final-rebind-table-semantics-l40s/outputs/20260726_202815_finance-v19-final-rebind-table-semantics-l40s`

QASPER v22 与 FinanceBench v20 都由当前代码提交生成，能用于当前行为诊断。但是两者
的 `run_provenance.index_contract` 仍为空，因此不能把版本间差异归因成“只改变了
代码”。

## 2. 为什么前几轮没有从根本解决

### 2.1 修复发生在 helper，系统不变量没有封口

前几轮已经增加 table block、statement/scope、final-evidence rebind、QASPER
answerability 和确定性计算，但允许其他路径绕过这些约束：

- QASPER verifier 能检查 quote 是否出现在 evidence，却没有保证 quote 蕴含问题中的
  关系；
- Finance QueryPlan 可以声明需要 operand，却仍允许一个含有多个数字的 page chunk
  填充该 slot；
- calculation verifier 检查 value 是否出现在 evidence，却没有要求该 value 绑定到
  唯一 cell/element；
- element index 有 `element_id`，但没有产出 `cell_id/table_id/row/column`，结构扩展
  因而在全部 80 条 Finance 预测中实际关闭。

结果是局部测试通过，但正式 route 仍可产生“形状合法、语义错误”的答案。

### 2.2 诊断指标把自洽误报为正确

Finance v20 中 11 个 execution status 为 `ok` 的计划全部被旧
cell/program/execution 指标记为 1，但只有 7/11 最终数值正确。这些字段测的是
“程序可运行且 verifier 接受”，不是“绑定了正确 gold operand 并得到正确答案”。

QASPER 的旧 token F1 还会给互斥答案非零分，例如：

- `unanswerable` 对 `yes` 为 0.2667；
- `unanswerable` 对 `no` 为 0.1429。

这不会改变旧 `avg_f1`，但必须增加 typed exact 指标，防止用字符重叠掩盖任务错误。

### 2.3 route 数量与模型调参掩盖了共同底层错误

- QASPER v22 的 controller 与 CRAG 输出 159/159 完全相同，三个 route 有
  145/159 完全相同；
- Finance v20 的 controller 与 CRAG 输出 20/20 完全相同，text/controller/CRAG 有
  15/20 完全相同。

因此多个 route 并没有提供相互独立的能力，汇总时却重复加权了同一底层输出。
temperature 已为 0 且设置 seed；继续只调 decoding、MMR 或 top-k，不能修复关系
蕴含、cell identity 或错误的 period/table 绑定。

## 3. 最新结果与根因

### 3.1 QASPER v22

| 指标 | v20 text | v22 text | v22 controller/CRAG | 判断 |
| --- | ---: | ---: | ---: | --- |
| native/token F1 | 62.77% | 67.50% | 67.57% | 总体改善 |
| semantic/exact | 56.60% | 64.15% | 64.78% | 总体改善 |
| boolean exact | 38/99 | 50/99 | 51/99 | 仍约一半错误 |
| unanswerable exact | 52/60 | 52/60 | 52/60 | 稳定 |
| evidence F1 | 19.34% | 19.34% | 17.10% | 相对 v20 基本不变 |
| verifier trace | 0/99 | 99/99 | 99/99 | 执行契约已关闭 |

477 条 trace 中 327 条为 `ok`、150 条为 `not_required`；prompt overflow 为 0，
275 条按预算截断。执行覆盖与预算问题已经关闭。

剩余 boolean 错误中，text route 49 条错误有 32 条上下文已经包含 gold span；
controller/CRAG 48 条错误有 29 条包含 gold span。这说明主要瓶颈已经从召回转为
关系判定。

当前实现的具体缺陷位于 `benchmark/qasper_answerability.py`：

- 对常规 `yes_complete/no_complete` verdict，只检查 quote 是否 grounded；
- `_boolean_quote_supports_relation` 只在 fallback verdict 分支执行；
- schema 正常返回 complete verdict 时，关系与极性保护被绕过。

真实失败 `b065...` 问 “fine-tuning 是否 required”，gold 为 `no`。模型引用了
“可以直接使用”的真实句子，却输出 `yes`。引用真实只证明句子存在，不证明
“required”这一关系成立。

修复必须让所有 boolean verdict 同时满足：

1. quote 存在于实际发送的 evidence；
2. quote 支持问题中的关系和极性；
3. `required/necessary/must` 与 `can/support/compatible` 不可互换；
4. 关系校验失败时保留受证据支持的候选或 abstain，禁止单 judge 无依据翻转。

### 3.2 FinanceBench v20

| 指标 | v19 | v20 | 判断 |
| --- | ---: | ---: | --- |
| token F1 | 10.05% | 13.40% | 改善但仍低 |
| semantic F1 | 23.33% | 31.96% | 改善 |
| native numeric | 15.00% | 8.75% | 明显回退 |
| page hit | 35.00% | 40.00% | 改善 |
| Reranked Recall@10 | 35.56% | 25.83% | 回退 |
| all-gold-pages hit | 21.25% | 16.25% | 回退 |
| false abstention | 15.00% | 17.50% | 回退 |
| element locator | 21.25% | 16.25% | 回退 |

结构 trace 证明当前“table identity”没有进入可执行索引：

- 80 条中 51 条报告 element index 存在；
- `structure_expansion_enabled=0/80`；
- `structure_metadata_coverage=0/80`；
- 313 条最终 evidence 中 `cell_id/table_id/row_label` 覆盖均为 0。

根因链是：

```text
page chunk
  → table-like element 只有 element_id
  → QueryPlan 允许 page 数字填 slot
  → adapter 在整页寻找 expected value
  → verifier 只验证 value/period/unit 出现在整页
  → 错误 operand 仍被判定为 valid
```

三个 artifact 失败形状直接证明该链路：

- `04854`：gold 为 `3676.2 - 460.8 = 3215.4`。adapter 把 3215.4 绑定成
  capex，得到 460.8；verifier 仍判 valid，两个 operand 都没有 cell ID。
- `00563`：正确 AMD page 48 已召回，但 segment parser 扫描页面上的所有 item row，
  把 “Each Of The Three Years In The Period Ended December” 当实体，没有先验证
  table 的 segment statement/scope。
- `01928`：问题要求 FY2023 adjusted EBITDA，gold 为 2018m；最终选中
  “Three Months Ended”季度表的 540。QueryPlan 只有 year，没有
  `fiscal_year/quarter/three_months/twelve_months` 粒度。
- `10499`：COGS slot 已填，2018/2019 consolidated inventory 缺失；因为结构扩展
  未启用，系统无法沿 table/cell identity 补齐两个 balance-sheet operand。

修复不能继续用 expected numeric answer 反向在 page 中找值。必须先建立 cell identity，
再允许计划执行：

1. table element 生成稳定 `table_id`；
2. parseable cell 生成 `cell_id/row/column/label/period/value/unit/scale`；
3. required numeric slot 在结构可用时只能由 cell/table element 填充；
4. plan operand 必须回溯到唯一 cell 或原子 element；
5. statement、financial scope 和 period granularity 必须一致；
6. 任一 operand 只能绑定到含多个候选数字的 page 时，verifier 必须拒绝执行。

### 3.3 评测不变量与可比性

当前仍有四个评测层问题：

1. `page_hit` 同一字段混合 strict gold page 和 evidence-aligned fallback；
2. 旧 calculation stage metrics 把 verifier 自洽当作答案正确；
3. QASPER token F1 对互斥 typed answer 给非零分；
4. artifact 的 `index_contract` 为空，无法做不可变输入上的 paired A/B。

修复保持旧字段不变，新增：

- `strict_page_hit` 与 `equivalent_evidence_page_hit`；
- `binding_verifier_pass_rate`、`program_validity_rate`、
  `execution_success_rate` 与 `executed_answer_accuracy`；
- `qasper_typed_accuracy`；
- manifest 文档内容与关键参数的稳定 `index_contract` digest。

## 4. 当前开放问题

| ID | 优先级 | 状态 | 根因 | 本轮修复 | 关闭标准 |
| --- | --- | --- | --- | --- | --- |
| FIN-STRUCTURE-CONTRACT-005 | P0 | 已实现，待 artifact | element index 未生成 table/cell identity，结构覆盖为 0 | 可解析表格现生成 table record 与 atomic cell records；DocQA 数值 route 自动合入 element index 并强制结构候选 | 新 artifact 的 table/cell identity 非零；structure coverage 非零；`10499` 能定向绑定或明确缺 slot |
| FIN-CELL-BINDING-006 | P0 | 已实现，待 artifact | page-level value presence 被当作 operand provenance，且 adapter/scale helper 对 `element_id/evidence_id` 的优先级不一致 | QueryPlan 拒绝明确的 page-only operand；verifier 拒绝非原子多数字绑定；Finance helper 统一以 `evidence_id` 回溯 item | `04854` 不再以错误 operand 通过 valid；所有成功 plan 的 operand 可回溯到 cell/atomic element |
| QASPER-RELATION-GUARD-005 | P0 | 已实现，待 artifact | complete verdict 绕过 relation entailment | 所有 complete yes/no verdict 统一执行 grounded + relation + polarity guard；required/can modal 关系单独校验 | 159×3 execution error=0；boolean exact 不低于 v22；已知 required/can 反例不再错误翻转 |
| BENCH-TYPED-METRIC-004 | P0 | 已实现，待 artifact | 字符 token F1 对互斥 typed answer 给非零分，execution 指标只测自洽 | 保留旧 F1，新增 `qasper_typed_accuracy` 与四个显式 calculation stage 指标 | QASPER typed conflict 为 0；execution ok 但 numeric wrong 时 executed-answer accuracy 为 0 |
| BENCH-PAIRED-002 | P0 | 已实现，待 artifact | `index_contract` 为空 | 两类 Slurm 脚本在运行前计算 manifest 与所有文档内容的 SHA-256 digest 并写入 provenance | 新 artifact 的 index contract 非空；paired 比较能拒绝不同 digest |
| FIN-PERIOD-GRANULARITY-001 | P1 | 已实现，待 artifact | slot 只绑定 year，不区分季度/全年 | QueryPlan、element 与 cell 传播 period kind，显式季度/全年冲突不再填 slot | `01928` 不再绑定 Three Months Ended；period mismatch trace 可见 |
| FIN-SEGMENT-SEMANTICS-002 | P1 | 已实现，待 artifact | segment argmax 扫描无关 table item，缺 statement/scope gate | 有明确非 segment statement 的 item 被排除；日期/期间表头伪实体被过滤 | `00563` matrix 不含日期表头伪实体；证据齐全时确定性返回 Data Center |
| EVAL-LOCATOR-002 | P1 | 已实现，待 artifact | strict locator 与等价事实页混在旧 `page_hit` | 保留旧字段，新增 `strict_page_hit` 与 `equivalent_evidence_page_hit` 并汇总到 route/summary | prediction/route/summary 均能独立报告两个口径 |
| BENCH-ROUTE-AGG-003 | P1 | 部分实现 | 等价 route 重复加权，不能代表独立能力 | summary 新增 `route_output_agreement_rate`；本轮不重定义历史主指标 | 发布前声明单一部署 route 或独立 route policy；主结论不把相同输出当独立增益 |
| RERANK-TRACE-001 | P1 | 开放 | 上游存在 reranking score，但 bundle trace 仍可能 `not_recorded` | 保留真实上游分数并记录 backend/model/executed/reason | trace 可区分“上游已重排”“本层未执行”“完全未重排” |
| RELEASE-001 | P1 | 被 P0 阻塞 | 尚无本轮真实聚焦 artifact | 只提交 QASPER 159×3 与 Finance 20×4 聚焦任务 | P0 由真实 artifact 关闭后才允许全量重跑 |

## 5. 本轮实施顺序

保护测试必须先于生产代码提交：

1. Element IR：table/cell identity、statement/scope、period kind 和 provenance；
2. QueryPlan：数值 slot 不接受 page-only evidence；
3. verifier：含多个候选数字且无 cell identity 的 operand 必须失败；
4. segment：非 segment table 与表头伪实体不得进入比较矩阵；
5. QASPER：complete verdict 也必须经过 relation guard；
6. metric：typed conflict、strict/equivalent locator、execution self-consistency 与
   gold correctness 分离；
7. Slurm：index contract 必须写入每个新 artifact。

保护测试已在旧实现上按预期 8/8 失败，并先提交为 `c47596f`。生产实现随后提交为
`6965bb6`。旧 `avg_f1`、`avg_native_score`、`avg_mara_score`、公开
`MARA`/`MARA-cli` 命令与用户参数均未改变。

## 6. 验收与回退保护

本地门槛：

- 新保护测试首次在旧实现上失败；
- 相关 benchmark 与 `libs/ktem/ktem_tests` 聚焦测试通过；
- 完整 `benchmark/tests` 与完整 `libs/ktem/ktem_tests` 通过；
- codebase hygiene 通过，不刷新 baseline；
- changed-files pre-commit 通过；
- 仓库根目录不产生 `data/`、`datasets/`、`outputs/`。

本轮实际结果：

- 根因保护测试：旧实现 8 failed；实现后 8 passed；
- 扩展聚焦回归：177 passed，随后重构后 166 passed；
- 完整 `benchmark/tests + libs/ktem/ktem_tests`：1813 passed；
- codebase hygiene：通过，未更新
  `scripts/codebase_hygiene_baseline.json`；
- changed-files pre-commit：全部通过；
- 两类 Slurm 脚本 `bash -n` 通过；
- QASPER manifest 的本地 index contract 试算得到合法
  `sha256:<64 hex>`；
- storage preflight：`.venv`、UV/HF/DocQA runtime 位于 fastscratch；
  fastscratch 约 137.4 GiB、446304/500000 files；仓库根目录没有
  `data/`、`datasets/`、`outputs/`。

聚焦 artifact 门槛：

- QASPER 159×3：477/477 可用、execution error=0、boolean trace coverage=100%、
  boolean exact 不低于 v22；
- FinanceBench 20×4：80/80 可用、index contract 非空、cell/table identity
  coverage 非零；错误 plan 不再以 verifier valid 通过；
- 重点逐条检查 `04854`、`00563`、`01928`、`10499`；
- 报告 strict/equivalent locator、typed accuracy、executed-answer accuracy 和 route
  agreement，不用旧综合分掩盖阶段失败。

如果新结构索引没有产生 cell identity，或成功 plan 仍无原子 provenance，本轮即判
失败，回到 index/IR 层修复，禁止继续用 prompt、阈值或 gold 特判补分。

## 7. 已关闭问题

- **QASPER task-contract coverage 与 prompt overflow：** v22 的 99×3 boolean
  trace 全覆盖，execution error=0；不再作为开放问题。
- **QASPER typed 输出形状：** 159/159 合法；保留 typed correctness 作为新指标问题。
- **Finance final-evidence rebind：** v19 已证明进入正式 route；当前问题是底层
  provenance 不原子，不再重复记录 slot-state 绕过。
- **page table block 拆分代码是否存在：** 已实现；当前未关闭的是拆分后仍没有可执行
  cell identity，二者不能混为一谈。
- **最终答案文本重复：** finalizer 后重复率为 0；route 输出相同属于聚合诊断问题，
  不是答案文本去重问题。
- **确定性计算器是否存在：** 已存在且能执行；当前问题是输入绑定和正确性指标，
  不再记录成“缺少执行器”。
