# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-28

## 1. 当前结论

本轮以 `Dev` 提交 `bf96c742c79e82676b17082c4d0020ccea4afe86` 的复核报告为
输入，对报告仍列出的 10 个 P0 和实际列出的 15 个 P1 逐项核对调用链、先写失败保护
测试，再修复 runtime、Evidence IR、benchmark projection 和 release gate。

报告中的代码级问题目前均已关闭，包级回归和代码卫生检查通过。主要结果是：

- manifest/runtime element adapter 在进入 Evidence IR 前保留 cell/span、row/column、
  period/value/unit/scale/currency 和 statement scope，去重使用 canonical atomic
  identity；
- `EvidenceSlot.locator` 结构化保存 source/page/element/figure/table locator，跨页
  slot 按实际 locator 绑定，不再依赖证据正文恰好出现 “page 9”；
- calculation verifier 与 citation projection 复用同一 synthetic-cell materializer；
  execution 只验证结果 claim，额外解释 claim 仍逐条验证；
- multi-period numeric 优先保留 metric/period；required-slot reservation 保留
  source-page diversity；page image 不再在 slot protection 前截断；
- `canonical candidate → post-fusion → reranker input → reranked → selected → generation context → verified support → emitted citation` 均为不同且真实的阶段；
- page/source citation 可通过统一 identity round-trip，atomic citation 同时约束 kind、
  identity、source 和 page；generic fallback 合并全部 verified support citation；
- canonical identity 对分隔符做无歧义转义，同时保留 legacy alias；strict reranker
  lineage 只接受 canonical 或显式 immutable input identity；
- headline manifest 要求恰好一个 deployed policy，或显式声明一个共享 ensemble
  policy；配置不完整时 fail-closed；
- paired regression 按 dataset/example/route 对齐，记录 paired win/loss/tie 和
  bootstrap CI；semantic +8pp 保留为 capability target，不再阻塞 contract 修复；
- release gates 直接计算 identity collision、runtime→benchmark round-trip、citation
  provenance、reranker lineage 和缺失 execution slot 仍生成答案五项不变量。

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

## 3. 本轮已关闭的 P0

| P0                                      | 根因                                           | 已落实修复                                                                               |
| --------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| A. element adapter 丢 atomic 字段       | adapter 在 Evidence IR 前降级为 parent element | 完整投影 atomic/financial 字段；benchmark 与 runtime 去重共用 canonical identity         |
| B. QueryPlan 无结构化 locator           | page/figure/table 只存在于 query 文本          | 新增 `EvidenceLocator`；slot score 对 source/page/element/figure/table 字段做确定性匹配  |
| C. verifier 找不到 synthetic cell       | calculation lookup 把 cell identity 映射回父表 | lookup、verifier 和 citation 共用 materialized cell record                               |
| D. 正确数值掩盖错误解释                 | execution value 一次性支持整段答案             | execution 只验证包含结果值的 claim，其余 claim 继续走 typed/domain/general verifier      |
| E. multi-period branch 丢 metric/period | generic multi-evidence 分支先命中              | multi-period numeric 优先生成逐 period operand slot                                      |
| F. shortlist 不保留 locator diversity   | 每 slot top-2 可来自同一页                     | required reservation 联合保护 source-page diversity                                      |
| G. page-image 前置截断                  | rank 20 后证据进不了 slot restore              | 所有 page image 先 canonicalize/slot reserve，再执行统一预算                             |
| H. fusion 与 reranker input 同义        | trace 把 shortlist 冒充 post-fusion            | post-fusion 保留完整排名，reranker input 记录真实 80 条输入；learned reranker 在此后执行 |
| I. QASPER 改答案保留 verifier state     | citation 清除但 answer-dependent state 未失效  | 同时失效 verified/claim/guardrail/observability state                                    |
| J. citation 按 page-only 选 source      | 多文档同页发生 cross join                      | 使用显式 source alias 映射，并以 source+page 合取解析；歧义时不猜测                      |

## 4. 本轮已关闭的 P1

| P1                                       | 已落实修复                                                               |
| ---------------------------------------- | ------------------------------------------------------------------------ |
| 1. citation kind 未匹配                  | atomic citation 必须与 `identity_of(item).kind` 一致                     |
| 2. page/source identity 不可 round-trip  | locator-only record 具有稳定 page/source identity                        |
| 3. generic fallback 只引用第一条         | 对全部 verified support 做稳定 citation union                            |
| 4. lineage 允许内容级 fallback           | 删除 source+page+text 和 kind-less element fallback                      |
| 5. boolean 同时有支持/反证仍 supported   | 返回 `conflicting` claim result，最终决策为 unknown                      |
| 6. graph `#source` 解析错误              | 分别解析 `#page:`、`#source` 并去除 marker                               |
| 7. span 依赖 evidence_level              | 优先级固定为 cell → span → table cell → element                          |
| 8. runtime_source_id 未进入 identity     | source identity 增加 runtime source 输入                                 |
| 9. identity key 分隔符碰撞               | `%`/`:` 做无歧义转义，legacy key 仅作为兼容 alias                        |
| 10. compact artifact 丢 identity         | 保留 identity/span/evidence_level/lineage/representations 及全部阶段列表 |
| 11. headline policy fail-open            | manifest role 存在时强制单 deployed policy 或显式 ensemble               |
| 12. paired regression 只是均值相减       | 逐样例对齐、timeout 配对、win/loss/tie 和 bootstrap CI                   |
| 13. contract gate 缺 evidence 不变量     | 新增并实际计算五项 contract invariant                                    |
| 14. Finance adequacy 允许部分字段缺失    | 任一 required field 缺失即阻止 generation                                |
| 15. claim aggregation 仍是 token Jaccard | 使用 subject/relation/value/unit/time/scope/polarity typed claim key     |

## 5. 当前验证证据

| 验证                     | 结果                     |
| ------------------------ | ------------------------ |
| P0/P1 定向跨模块测试     | 30 passed                |
| `benchmark/tests`        | 517 passed，6 warnings   |
| `libs/ktem/ktem_tests`   | 1447 passed，45 warnings |
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
   `canonical_candidate → fused → reranker_input → reranked → selected → generation_context → execution_operand → verified_claim_support → emitted_citation`。
3. 任一 identity、slot、stage 或 citation contract violation 非 0，停在首次断裂阶段修复，
   不调 reranker、MMR 或 prompt 掩盖。
4. smoke 通过后运行 QASPER 159×3 与 FinanceBench 20×4 聚焦验证。
5. 聚焦验证通过 contract gates、paired regression、semantic calibration 和 latency
   coverage 后，再决定是否运行全量 benchmark。
