# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-28

## 1. 当前结论

本轮以 `Dev` 提交 `9063727e15425c2b45723a8a993f89d94ff47c56` 的复核报告为
输入，对报告列出的 11 个 P0 和 13 个 P1 逐项核对实际代码、先写失败保护测试，再
修复运行时与 benchmark 契约。

报告中的 24 个代码级问题目前均已关闭，包级回归和代码卫生检查通过。主要结果是：

- citation locator 同时约束 evidence identity、source 和 page；page/source 引用保持
  自身粒度，不再扩散成整页所有 cell；
- generic citation 只来自 claim verifier 确认的支持证据，答案变更会清除旧 citation
  并重新绑定；
- numeric verifier 使用已验证的 calculation plan 和确定性 execution 结果，不再只用
  答案与 operand 文本重叠判断派生数值；
- numeric、boolean、visual 和 cross-page capability 可以组合成多个必需 slot，并能
  约束不同 source-page；
- candidate、reranker input、reranked、selected、generation context、verified 和
  emitted citation 阶段有独立且可审计的 identity/coverage；
- headline 使用 manifest 声明的 deployed policy，不再通过固定 route 名猜测部署策略；
- release gates 已拆成 contract、judge calibration、paired regression 和 capability
  target 四类。

这些结论只说明静态代码契约和本地单元测试已闭合，不说明数据集指标已经达标。本轮
没有生成新的 QASPER/FinanceBench artifact，也没有提交 Slurm benchmark 任务。在
完成真实 2–5 条 smoke 和聚焦验证前，仍不建议直接运行全量 benchmark。

本轮未改变公开 `MARA`、`MARA-cli` 或 `MARA docqa` 命令与参数。

## 2. 为什么此前修复会反复回退

此前把问题表现为多个独立的 reranker、MMR、prompt 或 verifier bug，但真正导致
回退的是同一事实在不同阶段使用了不同身份、粒度和阶段含义：

```text
runtime evidence
→ candidate
→ fusion/reranker input
→ reranked
→ evidence-set selection
→ calculation/generation
→ claim verification
→ emitted citation
→ benchmark projection
→ metric
```

具体断裂包括：

- local cell ID 曾绕过 citation 的 source/page 约束，page citation 又会扩散到整页
  原子证据；
- `cited_evidence` 曾混用“verifier 认为支持”和“最终答案实际输出引用”；
- calculation execution 已经存在，但通用 numeric verifier 没有消费 execution value
  与全部 operand provenance；
- cross-page 只表达一个泛化 support slot，任一页命中就会虚假填满；
- element candidate 在 slot restore 前被固定截断，reranker metric 又使用推测的前 80
  而不是真实输入；
- headline page hit 曾读取 candidate，stage identity 又没有 kind，导致 cell/span
  同 local ID 时错误命中；
- QASPER verifier 改变 answer polarity 或改成 unanswerable 后，旧 citation 仍被复用；
- route、retriever、query 和 score stage 混在同一 trace key 或分数空间中。

因此本轮的关闭标准不是“修改了某个函数”，而是同一 contract 同时在运行时、投影、
指标和跨模块回归测试中成立。

## 3. 已关闭的 P0

| P0                                               | 根因                                        | 已落实修复                                                                                             | 保护证据                               |
| ------------------------------------------------ | ------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------- |
| 1. exact citation 绕过 source/page               | local ID 被当成全局 ID                      | citation 使用 evidence/source/page 合取匹配；裸 local ID 必须有 source                                 | cross-source/cross-page citation tests |
| 2. page citation 扩散原子证据                    | locator 粒度和 evidence 粒度混用            | page/source citation 生成单一 locator record，不复制整页 cells                                         | page citation granularity tests        |
| 3. generic fallback 引用首候选                   | retrieved 被误当成 supported                | 只允许 `verified_claim_support_evidence` 自动生成 citation                                             | unsupported candidate tests            |
| 4. calculation execution 未进入 numeric verifier | 通用 token verifier 无法验证派生值          | typed verifier 核对 plan、execution value、unit/scale 和全部 execution citation                        | derived value/mismatch tests           |
| 5. numeric/boolean cross-page 能力互斥           | 单一 question type 覆盖 capability          | numeric 生成左右 operand；boolean 生成 proposition 与左右 support；必要 slot 要求 distinct source-page | cross-page plan tests                  |
| 6. element 在 slot restore 前截断                | element index 固定只供给 20 条              | element 全量进入 canonical candidate，再按 required-slot quota 和全局预算选择                          | rank-21 required element test          |
| 7. reranker metric 使用推测输入                  | benchmark 用 `candidate[:80]` 代替执行输入  | runtime 记录 `reranker_input_evidence`，lineage/coverage 使用该阶段                                    | actual reranker input test             |
| 8. headline all-gold-pages 读取 candidate        | 召回与最终证据混为一项                      | headline 使用 generation context/selected；candidate hit 仅作阶段诊断                                  | candidate-only page test               |
| 9. span 投影优先级错误                           | parent element 覆盖 atomic span             | 投影优先级为 cell → span → element                                                                     | span projection test                   |
| 10. QASPER 冲突保留错误答案                      | verifier verdict 与 candidate polarity 分叉 | 有 grounded opposite verdict 时纠正 polarity；不足证据时输出 unanswerable                              | QASPER polarity tests                  |
| 11. 答案改变复用旧 citation                      | answer 与 citation 没有共同版本             | answer contract 改变答案时清空 structured/predicted/cited/verified support，等待重新绑定               | answer-change citation test            |

## 4. 已关闭的 P1

| P1                                                        | 已落实修复                                                                                     |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 1. reranker lineage 接受跨 source 裸 local/text hash      | lineage 只接受 canonical 或 source-scoped identity                                             |
| 2. RRF 生成 synthetic modality list、合并不同 query       | 保留真实 dense/sparse/graph lineage；rank list key 包含 retriever、round、query                |
| 3. modality equality 过严                                 | 通过明确 compatibility matrix 支持 figure/table/formula/slide 与 page image/element            |
| 4. simple visual 没有 required slot                       | 新增 `support:visual_primary`                                                                  |
| 5. representations 未进入推理且 aggregate subset 被判冲突 | text/OCR/VLM/caption 进入统一 representation；非原子 aggregate 允许事实子集/超集               |
| 6. boolean 否定问题和解释型答案不稳定                     | typed boolean verifier 同时处理 question negation、yes/no polarity 和解释文本                  |
| 7. 单 graph backref 不投影 locator                        | 单 backref 也解析 source/page，并优先使用 top-level locator                                    |
| 8. 整个 runtime turn 被记为 generation                    | `runtime_turn_seconds` 与 pipeline `generation_seconds` 分离                                   |
| 9. `identity_of()` 信任陈旧 embedded identity             | 始终从当前字段重算；canonicalization 对 expected identity 不一致抛 contract error              |
| 10. stage identity 缺少 kind                              | stage/gold key 统一为 source、page、kind、local ID                                             |
| 11. headline 硬编码 `controller_auto`                     | manifest 用 `headline_role=deployed_policy` 明确部署策略；旧 artifact 才走兼容回退             |
| 12. release gate 类型混杂、paired regression 不完整       | 四类 gate 分组；增加 native、false abstention、citation 和 execution error paired delta        |
| 13. identity tests 只是固定样例                           | 引入 Hypothesis，覆盖 source/kind/table/year/alias/continuation/representation/bbox 组合不变量 |

完整测试还暴露并关闭了三项伴随回归：

- prediction completion 的 `headline_role` 投影漏传 route；
- selection 曾对每个 score field 单独归一化后取最大，单一 modality 分数会虚假压过
  query anchor；现在每轮只采用一个可审计的 score stage；
- required-slot 选择只看 slot 文本覆盖率；现在把真实 reranker relevance 纳入边际得分，
  但不把 first-stage fusion 分数冒充 reranker。

## 5. 当前验证证据

| 验证                     | 结果                     |
| ------------------------ | ------------------------ |
| P0/P1 定向跨模块测试     | 45 passed                |
| `benchmark/tests`        | 504 passed，6 warnings   |
| `libs/ktem/ktem_tests`   | 1430 passed，45 warnings |
| codebase hygiene ratchet | passed；未刷新 baseline  |
| 新 benchmark artifact    | 尚无                     |
| 新 Slurm 任务            | 未提交                   |

warnings 为现有第三方弃用/版本提示，不是本轮新增失败。单元测试证明代码不变量成立，
不证明真实 parser、runtime adapter、模型输出或数据集分数已经达标。

## 6. 最新开放问题表

这里只保留不能由本轮静态代码和本地测试真实关闭的事项。

| ID                    | 优先级 | 状态                      | 根因与当前缺口                                                                                                        | 关闭标准                                                                                                  |
| --------------------- | ------ | ------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| CONTRACT-ARTIFACT-001 | P0     | 待真实 artifact 验证      | 真实 parser、adapter、模型输出仍可能不满足单元测试中的 identity/stage/citation contract                               | Finance/QASPER 各 2–5 条 smoke 中全阶段 lineage 100%、contract violation=0；之后完成聚焦验证              |
| FIN-ATOMIC-SUPPLY-011 | P0     | 代码就绪，真实 PDF 未证实 | wrapped row、跨页 table continuation、局部 scale 和 period header 是否稳定产出 atomic cell 只能由真实 artifact 证明   | 困难样例 operand/dimension 全部可回溯；缺失 requirement 时不执行；citation 覆盖所有 operand               |
| SEMANTIC-JUDGE-020    | P1     | 待人工校准 artifact       | 没有冻结 200 条人工标注，不能从代码推断 judge 一致率                                                                  | 冻结 200 条；coverage≥99.5%，人工一致率 ≥90%，核心冲突不得判 supported                                    |
| VERIFY-FREETEXT-028   | P1     | 待校准验证                | deterministic verifier 已覆盖 numeric/boolean/year/direction/negation；开放域主体、关系、条件与作用域仍需要冻结集校准 | 按 answer type 报 precision/recall；错误主体/关系/作用域不通过；所有 supported claim 有 atomic provenance |
| LATENCY-PAIRED-008    | P1     | 已埋点，待 artifact       | stage timing 已拆分，但尚无同样例、同 route 的本轮 paired artifact                                                    | timing coverage=100%；简单 QA 中位增幅 ≤20%，复杂 QA≤50%                                                  |

## 7. 下一步顺序

1. 先生成 FinanceBench 和 QASPER 各 2–5 条 smoke artifact。
2. 逐条检查
   `candidate → fused → reranker_input → reranked → selected → generation_context → execution_operand → verified_claim_support → emitted_citation`。
3. 任一 identity、slot、stage 或 citation contract violation 非 0，停在首次断裂阶段修复，
   不调 reranker、MMR 或 prompt 掩盖。
4. smoke 通过后运行 QASPER 159×3 与 FinanceBench 20×4 聚焦验证。
5. 聚焦验证通过 contract gates、paired regression、semantic calibration 和 latency
   coverage 后，再决定是否运行全量 benchmark。
