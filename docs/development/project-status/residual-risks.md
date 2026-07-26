# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-26

最新已完成 artifact 代码：`19612204c6544ec1230e1e5dc2dbae0bc02c66f0`

当前候选状态：根因修复提交 `fc12790`；QASPER verifier prompt-budget
补丁已完成本地验证，待重新提交聚焦任务

发布结论：**仍有 P0 验证与可比性阻塞，不应直接重跑全量 benchmark。**

## 1. 文档边界

本文只记录三类事实：

1. 最新 artifact 中仍能复现的问题；
2. 能由当前执行路径解释的根因；
3. 已有保护测试和代码实现、但尚待真实 artifact 验证的修复。

“分数下降”不是根因。阈值、prompt 或评分权重变化只有在修复了任务契约、
证据身份、表格绑定或执行不变量时才属于有效修复。已经被最新运行关闭的问题从
开放表移除；尚无证据的推测不写入本文。

本轮实际读取的 artifact：

- QASPER v20，159 个样本 × 3 个 DocQA route，共 477/477 条可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/qasper-typed-v20-invariant-guard-l40s/01_core_text/20260726_200412_qasper-typed-v20-invariant-guard-l40s-9949298`
- QASPER v19 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-qasper-typed-v19-semantic-proposition-identity-l40s/01_core_text/20260726_161424_residual-qasper-typed-v19-semantic-proposition-identity-l40s-9945264`
- FinanceBench v19，20 个样本 × 4 个 route，共 80/80 条可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/finance-v19-final-rebind-table-semantics-l40s/outputs/20260726_202815_finance-v19-final-rebind-table-semantics-l40s`
- FinanceBench v18 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-finance-v18-semantic-binding-lineage-l40s/outputs/20260726_172006_residual-finance-v18-semantic-binding-lineage-l40s`

这些目录当前都存在。QASPER v20 和 Finance v19 的 `run_provenance.git.commit`
均为 `1961220`；两者的 `index_contract` 仍为空，因此可以做行为诊断，但不能完成
“同一不可变索引上的代码 A/B”因果归因。

## 2. 最新结果与已证实根因

### 2.1 QASPER v20

text route 的最新结果：

| 指标                       |     v19 |     v20 | 判断            |
| -------------------------- | ------: | ------: | --------------- |
| native/token F1            |  64.67% |  62.77% | -1.90 pp        |
| semantic F1                |  62.26% |  56.60% | -5.66 pp        |
| boolean exact              |   51/99 |   38/99 | 明显回退        |
| unanswerable exact         |   48/60 |   52/60 | 改善            |
| typed 结构合法率           | 155/159 | 159/159 | 已关闭          |
| QASPER answerability trace |   99/99 |    0/99 | verifier 被绕过 |

根因不是 verifier prompt 仍不够好，而是 **任务契约绑定在错误的执行层**：

- `verify_qasper_answerability` 只在
  `benchmark.system._generate_benchmark_answer` 中执行；
- v20 manifest 的三个正式 route 均走 `DocQARuntimeEngine`；
- `benchmark.runner` 在 engine 输出后没有统一的 QASPER task-contract stage；
- 所以 v20 的 99 条 boolean 全部没有 `qasper_answerability` trace。此前已有的
  proposition/polarity 修复根本没有进入这次被评测的路径。

这也解释了为什么多轮局部测试可以通过而 benchmark 仍回退：测试验证了 helper，
却没有验证“所有正式 engine 必须经过同一个任务契约”的系统不变量。

本轮修复把 QASPER answerability 移到 runner 的 engine-independent stage：
先由 finalizer 把长解释规范化为 `yes/no/unanswerable`，再执行 verifier；若 verifier
改变答案，重新 finalization 后才评分。旧 text system 已产生 trace 时不会重复调用。
Slurm artifact validator 现在还可以强制要求所有可用 boolean prediction 都有 trace。

首次验证任务 `9952343` 还暴露了第二个执行不变量缺口：统一 verifier 已经实际进入
正式 route，但它直接拼入未限长的聚合 evidence。第一条 boolean 的 prompt 至少为
3905 input tokens，再预留 192 output tokens 后超过本地 Qwen3-8B 服务的 4096
上下文并以 HTTP 400 终止。该失败发生在服务健康检查和索引创建之后，与 Slurm
资源、单卡共置或依赖链无关。

当前 `qasper_answerability.v11` 在 LLM 调用前按检索顺序保留完整高排名段落，并将
verifier prompt 限制在 7000 字符内；quote grounding 只检查实际发送给 verifier
的证据。trace 新增原始/使用 evidence 字符数、prompt 字符数和截断状态。保护测试
使用本地 Qwen tokenizer 验证长证据压力样例经 chat template 后为 771 input
tokens，加 192 output tokens 后共 963，低于 4096；不通过捕获异常或跳过契约来
制造可用结果。

### 2.2 FinanceBench v19

四 route 汇总：

| 指标               |    v18 |    v19 | 判断                 |
| ------------------ | -----: | -----: | -------------------- |
| token F1           | 12.16% | 10.05% | -2.11 pp             |
| native numeric     |  7.50% | 15.00% | 改善                 |
| semantic F1        | 23.00% | 23.33% | 基本持平             |
| page hit           | 33.75% | 35.00% | 小幅改善             |
| Reranked Recall@10 | 32.50% | 35.56% | 改善                 |
| all-gold-pages hit | 21.25% | 21.25% | 无变化               |
| slot coverage      | 75.56% | 72.22% | 仍不可信             |
| execution accuracy | 37.50% | 45.83% | 改善                 |
| unit accuracy      | 83.33% | 75.00% | 指标口径混入失败执行 |
| false abstention   | 17.50% | 15.00% | 改善                 |
| reranker lineage   |   100% |   100% | 已关闭               |

v19 证明 final-evidence rebind 已经生效：

- `00882` 与 text-route `10285` 可以用最终证据重新授权；
- `03531` 的衍生品错表仍被拒绝；
- `01928` 的 adjusted EBITDA 已恢复；
- 因此 `FIN-SLOT-STATE-003` 与 adjusted-EBITDA 专项检索问题已关闭。

仍未解决的失败不是一个问题，而是三个不同层级。

#### A. 整页被伪装成一个 table element

`element_parser._looks_like_financial_table` 只要在整页 chunk 中看到财务报表提示词和
若干数值行，就把整页建立为一个 table element。结果是：

- 同一 `element_id/table_id` 可能跨过多个真实表格和中间叙述；
- `10499` 中一个 page-level element 可以同时“支持”COGS、inventory、养老金等
  无关字段；
- 后续去重、slot binding 和 verifier 看到的身份从一开始就是错的，增加 reranker
  或 top-k 无法恢复真实表格边界。

本轮改为从 page chunk 中产生多个 table block；每个 block 有独立 element ID，
并记录 `statement_kind` 与 `financial_scope`。显式 parser 已提供的 table element
保持原样，避免破坏已有高质量结构。

#### B. statement 正确不等于 scope 正确

`10499` 的库存错误不只来自 cash-flow 中的 inventory change。text route 还会命中
“Assets held for sale”表中的 2019/2018 inventories 21/92；它是库存余额，但不是
题目要求的 consolidated inventory。

因此简单规则“inventory 必须来自 balance sheet”仍不够。当前修复同时绑定：

- `statement_kind`：如 `income_statement`、`balance_sheet`、
  `cash_flow_statement`、`segment_table`；
- `financial_scope`：如 `consolidated`、`held_for_sale`、`acquisition`、
  `segment`。

这些字段已贯穿 `EvidenceElement → EvidenceSlot → FinancialTableCell → CalculationOperand → required-slot verifier`。inventory-turnover 的 COGS 必须来自
consolidated income statement，inventory 必须来自 consolidated balance sheet。

同时修复了一个独立年份绑定错误：问题明确写
“FY2019 COGS / average FY2018 and FY2019 inventory”时，旧
`target_year` 用 `periods[-1]` 错选 FY2018 COGS。现在 query plan 与数值执行器共享
同一显式公式年份解析。

#### C. segment argmax 不是普通 extractive QA

`00563` 要求比较 AMD 各 reporting segment 在 FY21→FY22 的比例增长，并排除
Embedded。旧 QueryPlan 只有两个宽泛的 `net sales + period` support slot，没有
entity×period 矩阵，也没有确定性 argmax；v19 最终没有召回 gold page 47。

gold evidence 还是纵向抽取表：

`Net revenue → Data Center/Client/Gaming/Embedded → 2022/2021 values`。

当前修复新增 `finance_segment_comparison.v1`：

1. QueryPlan 标为 `comparison_argmax`，检索 query 使用
   `reporting segment net revenue + period`；
2. 解析横向表和 FinanceBench 的纵向表抽取；
3. 按 `entity × period` 绑定 Decimal 值；
4. 排除问题点名的实体；
5. 至少两个剩余实体都有两期值时才计算
   `(current-prior)/abs(prior)` 并确定性 argmax；
6. 值不完整时返回 `insufficient_entities`，不让 LLM 猜。

本地 gold-shape 回归输出 `Data Center`，但检索能否把 page 47 放入最终 evidence
仍必须由新索引上的聚焦任务验证。

### 2.3 诊断指标曾把不同阶段混为一谈

v19 的 `slot_coverage=72.22%` 来自检索阶段 QueryPlan；它不等于最终 operand 已被
verifier 授权。旧 `unit_accuracy` 在执行失败时也可能计入 1，导致分母含义不稳定。

为了保持历史可比性，本轮没有重定义旧字段，而是新增：

- `retrieval_slot_coverage`：旧 retrieval-time slot coverage 的显式别名；
- `verified_slot_coverage`：最终 required slots 中实际通过重绑定的比例；
- `successful_execution_unit_accuracy`：只在 plan valid 且 execution ok 时计量。

## 3. 官方与成熟项目的处理方式

这些方案不能直接复制到 MARA，但它们共同说明应该固定什么不变量。

### QASPER

[官方 QASPER LED baseline](https://github.com/allenai/qasper-led-baseline)
分别报告 Answer F1 和 Evidence F1，并把有/无 evidence scaffold 作为独立实验。
它没有把某一个 engine 私有的后处理当成全任务契约。MARA 对应的约束是：

- typed output、answerability、评分必须在所有正式 route 的公共边界执行；
- answer 与 evidence 诊断分开；
- artifact 必须证明契约实际覆盖，而不是仅证明 helper 存在。

### FinanceBench

[FinanceBench 官方数据](https://github.com/patronus-ai/financebench)同时提供
`evidence_text`、零起始 `evidence_page_num` 和 `evidence_text_full_page`，论文结果
还使用人工正确性复核。它把答案、精确 evidence span 和 full-page locator 分开，
因此 MARA 也应保留 strict page hit，同时另报 equivalent-evidence，不能通过放宽
旧 page metric 掩盖 locator 问题。

### FinQA 与 TAT-QA

[FinQA 官方实现](https://github.com/czyssrs/FinQA)把 supporting facts
(`gold_inds`)、program 和 execution answer (`exe_ans`) 分开，并分别报告 program
accuracy 与 execution accuracy。官方还曾因 table-row 格式不一致和 label leak
主动修正并下调结果，说明输入/评测不变量比“保持高分”更重要。

[TAT-QA 官方格式](https://nextplusplus.github.io/TAT-QA/)保留二维 table、paragraph
ID、derivation、`answer_type`、`answer_from`、`req_comparison` 和 `scale`。这直接
支持 MARA 当前方向：先绑定单元格、表格来源、比较类型和 scale，再执行受限程序。

### HiTab

[HiTab 官方实现](https://github.com/microsoft/HiTab)保留完整 table matrix、
merged regions、cell coordinates、header hierarchy、linked entity/quantity cells
和公式引用。它在序列化前先找到 linked cells 及其祖先，而不是把整页文本贴上
“table”标签。MARA 本轮拆真实 table block、保留 table/cell/period/statement/scope
身份，正是为了恢复这一类结构不变量。

## 4. 当前开放问题

| ID                        | 优先级 | 当前状态                 | 根因                                                                                                          | 关闭标准                                                                                                           |
| ------------------------- | ------ | ------------------------ | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| QASPER-EXEC-CONTRACT-004  | P0     | v11 已实现，待重新验证   | answerability 过去只接在 legacy text system；移到 runner 后又暴露 verifier 聚合 evidence 无独立 prompt budget | QASPER 159×3 全部可用；execution error=0；99×3 boolean trace coverage 100%；validator 通过                         |
| QASPER-POLARITY-003       | P0     | 已实现，待聚焦验证       | v20 因契约未执行，无法验证 conflict-preservation 与 abstention recovery                                       | text route boolean exact/semantic 相对 v20 净提升，且非 abstain primary 无错误单-judge flip                        |
| FIN-TABLE-IR-004          | P0     | 已实现，待新索引验证     | whole-page pseudo-table 破坏 table identity；statement 与 scope 未贯穿执行链                                  | 新隔离索引中 table block ID 独立；`10499` 不绑定 cash-flow/held-for-sale inventory，正确 consolidated cells 可执行 |
| FIN-COMPARISON-001        | P0     | 已实现，待聚焦验证       | `00563` 缺 entity×period matrix 与 deterministic argmax                                                       | gold page 47 进入候选/重排/最终 evidence；trace 含完整非排除实体矩阵；答案为 Data Center                           |
| FIN-SEGMENT-RETRIEVAL-003 | P0     | 已实现 query，待聚焦验证 | 旧 query 只含 net sales+period，与文档的 reporting segment/net revenue 表述不对齐                             | `00563` Candidate Recall、Reranked Recall 与 page hit 均命中；第二轮只补缺失 segment slots                         |
| BENCH-PAIRED-002          | P0     | 开放                     | 最新 artifact 的 `index_contract` 为空，代码变化与索引变化不能隔离                                            | 建立只读不可变索引 snapshot digest；A/B 的 `paired_input_hash` 与 index contract 一致；报告 paired wins/losses/CI  |
| BENCH-STAGE-METRIC-003    | P1     | 已实现，待 artifact 验证 | retrieval fill、verified fill 与 failed-execution unit 被旧指标混在一起                                       | 新三项指标进入 prediction/route/summary，coverage 与分母符合定义                                                   |
| RERANK-TRACE-001          | P1     | 开放                     | lineage 已为 100%，但实际 backend/model/execution 状态仍可能为 `not_recorded`                                 | trace 明确 backend、模型、是否执行、输入/输出数量；未执行时显式记录原因                                            |
| EVAL-LOCATOR-002          | P1     | 开放                     | strict gold page 与等价事实页未分离，`04854` 类正确答案仍是 page miss                                         | 保留旧 strict page hit；新增有 provenance 的 equivalent-evidence diagnostic                                        |
| FIN-EVAL-001              | P1     | 开放                     | `04980` 的 4.625B 与 gold 4.60 不符合严格相对容差；官方开源集依赖人工评审，缺少可直接照搬的自动舍入契约       | 不修改旧 native；先定义并冻结有依据的 precision diagnostic，报告相对误差与显示精度，不使用任意放宽阈值             |
| FIN-UNIT-002              | P1     | 开放                     | 成功执行样本的单位/scale 覆盖仍未达到发布门槛                                                                 | `successful_execution_unit_accuracy ≥98%` 且 coverage 报告非空                                                     |
| RELEASE-001               | P1     | 被 P0 阻塞               | 真实聚焦 artifact 和不可变索引 A/B 尚未关闭                                                                   | 所有 P0 关闭后才允许一次全量重跑                                                                                   |

## 5. 本轮实际实现

保护测试先于生产代码加入，覆盖以下 artifact-derived 形状：

- QASPER：engine 投影完成后统一执行 task contract；已有 trace 不重复调用；
  非 QASPER 不受影响；Slurm validator 拒绝 boolean trace coverage 不完整的 artifact；
  verifier 长 evidence 在调用前受预算约束，grounding 不使用未发送证据。
- table IR：一个 page chunk 中的 income statement 与 balance sheet 被拆成两个
  element，正文不再跨表污染，statement/scope 独立。
- inventory turnover：FY2019 COGS 年份不再受问题中年份顺序影响；
  held-for-sale inventory 不能满足 consolidated inventory slot。
- segment comparison：横向 table 与 FinanceBench 纵向抽取都能绑定 entity×period；
  单实体或缺值时拒绝 argmax；route 集成只在 deterministic trace 为 `ok` 时返回。
- stage metrics：retrieval/verified slot coverage 分离；执行失败时
  `successful_execution_unit_accuracy=null`。

公开影响范围：

- benchmark runner 的 QASPER 离线任务契约与 Slurm artifact validation；
- 共享 DocQA 的 Finance QueryPlan、element/table identity、数值绑定和比较执行；
- additive benchmark trace/metric 字段。

不改变 `MARA`、`MARA-cli`、用户可见 CLI 参数、已有指标定义或持久化数据键。
新 table identity 只有在重建隔离 v2 索引后才能覆盖旧索引内容。

## 6. 已完成的本地验证

截至本次文档更新，已完成：

- 新增保护测试首次运行按预期在缺失模块/契约处失败；
- 第一组根因测试：52 passed；
- statement/scope、年份绑定、纵向表和 route 集成聚焦测试：85 passed；
- 较宽 benchmark + Finance/evidence 回归：563 passed，发现并修复两个测试 engine
  未实现新 task-contract interface 的问题后，失败用例 2/2 通过；
- 完整 `benchmark/tests`：461 passed；
- 完整 `libs/ktem/ktem_tests`：1343 passed；
- QASPER verifier prompt-budget 回归：30 passed；长证据压力样例经本地 Qwen
  chat template 后为 771 input + 192 output tokens；
- codebase hygiene：通过，未刷新
  `scripts/codebase_hygiene_baseline.json`；
- changed-files pre-commit：black、isort、flake8、mypy、codespell 等全部通过；
- storage preflight：`.venv` 与 Python 位于 fastscratch；UV/HF/DocQA runtime
  指向 fastscratch；fastscratch 为 136.6 GiB、441441/500000 files；仓库根目录
  不存在 `data/`、`datasets/`、`outputs/`。

本地实现和验证已完成；尚未完成的是新隔离索引上的聚焦 artifact 验收以及
`BENCH-PAIRED-002` 的不可变索引合同。

## 7. 下一步固定顺序

1. 提交前检查 diff，确认没有旧指标重定义、gold 特判或任意容差放宽。
2. 用新隔离索引提交两组聚焦任务：
   - QASPER 159×3，必须启用 `--require-qasper-answerability`，并确认
     execution error=0、trace 中存在 evidence budget 字段；
   - FinanceBench 20×4，重点核验 `10499`、`00563`、`04980`、`04854`。
3. 聚焦结果只用于行为验收；在 `index_contract` 仍为空时，不把分数差异声称为
   纯代码因果效果。
4. 只有 P0 全部关闭后，才讨论全量 benchmark 重跑。

## 8. 已关闭问题

- **QASPER typed 结构出口：** v20 为 159/159；不再作为开放问题。
- **Finance final-evidence rebind：** v19 的 `00882`、`10285` 通过，`03531`
  仍正确拒绝；`FIN-SLOT-STATE-003` 关闭。
- **Adjusted EBITDA 检索：** `01928` 已恢复；从旧 `FIN-RETRIEVAL-002` 中移除。
- **Reranker lineage：** v18/v19 均为 100%；只保留 backend observability 债务。
- **最终答案重复：** finalizer 后重复率为 0；生成层重复保留为非阻塞观察项。
- **跨证据确定性计算是否存在：** 已有多条成功样本；当前问题是语义身份、比较覆盖和
  检索，不再记录成“执行器完全缺失”。
