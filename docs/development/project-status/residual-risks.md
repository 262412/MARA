# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-28

## 1. 当前结论

本轮以 `Dev` 提交 `5dcf8d34a9fd4d4e53fb76d2f09ad8af2b72c81c` 的复核结果为
输入，逐项核对并修复其中仍列出的 8 个 P0 和 6 个 P1。代码级问题目前均已有
失败保护测试和实现修复，`benchmark/tests` 与 `libs/ktem/ktem_tests` 两个包级
测试集均通过。

本轮闭合的是证据契约和评测接线，不是数据集能力验收：

- parser、offline sidecar、persisted element index 和 benchmark manifest 共用同一个
  atomic element adapter；
- Evidence Identity、locator alias、QueryPlan slot、calculation、claim verification、
  emitted citation 和 benchmark projection 使用同一 canonical identity；
- candidate、post-fusion、reranker input、reranked、selected、generation context、
  verified claim support 和 emitted citation 分阶段记录和计量；
- release gate 对 identity、projection、citation 和 paired records 使用真实阶段数据，
  缺失配对样例时 fail-closed；
- compact artifact 保留 identity、atomic fact、locator、lineage、representation、
  OCR/VLM 和视觉定位审计字段。

本轮没有改变公开 `MARA`、`MARA-cli` 或 `MARA docqa` 命令、参数和 route API。
本轮也没有生成新的 QASPER/FinanceBench artifact 或提交 Slurm benchmark；因此不能
据此声称数据集分数、延迟或 semantic judge 已达标。

## 2. 根因总结

此前多轮修改反复出现“一项上升、另一项回退”，不是因为单个 reranker、MMR 或
prompt 参数不够好，而是同一事实经过不同阶段时会改变身份、locator、粒度或阶段
含义：

```text
parser / sidecar / persisted index
→ canonical Evidence IR
→ retrieval candidates
→ fusion / reranker input
→ reranked evidence
→ evidence-set selection
→ slot binding / calculation
→ claim verification
→ emitted citations
→ benchmark projection
→ metrics / release gates
```

本轮复核确认的断裂主要有四类：

1. ingestion 路径各自维护字段白名单和 raw-ID 去重，atomic cell/span 会在进入
   Evidence IR 前丢失或折叠；
2. QueryPlan、citation 和 metrics 对 source/page alias 的解释不同，正确证据可能在
   binding、citation backref 或 page coverage 任一阶段失配；
3. calculation、QASPER rewrite 和 generic verifier 会把旧答案状态、正确数值或单条
   支持错误扩展到未被支持的 claim；
4. release gate 使用错误阶段或聚合均值，导致指标名称与实际测量对象不一致。

因此关闭标准是同一 contract 在 runtime、projection、metric 和回归测试中同时成立，
而不是只修改一个调用点。

## 3. 本轮已关闭的 P0

| ID                               | 根因                                                                                        | 已落实修复与不变量                                                                                                                                                                                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P0-01 element ingestion 未统一   | offline sidecar 和 persisted index 仍使用旧字段白名单、raw `evidence_id` 与 first-wins 去重 | 新增共享 element record adapter；完整保留 cell/span、table、period/value/unit/scale、continuation、OCR/VLM、lineage、representations 和 scores；所有 ingestion 使用 canonical identity 去重，相同 atom 合并 provenance，冲突 atom 抛出 contract error |
| P0-02 locator 未贯穿 slot 分支   | boolean、Finance 和 multi-period 分支只要求“不同页”，未绑定问题中的显式页码                 | 所有 heuristic/Finance slot 接收 explicit page labels；一一对应时绑定单页，数量不能一一对应时保存允许页集合，并继续要求 required slot 的 source-page diversity                                                                                        |
| P0-03 locator normalization 分叉 | QueryPlan、citation、emitted citation 和 stage/page metrics 分别读取不同字段                | 建立共享 source aliases、page aliases、element labels、source-page locators 和 `locator_matches`；支持 dataset/parser page、source aliases 与 backrefs；figure/table label 进入 `EvidenceElement` 和 benchmark projection                             |
| P0-04 calculation 复合句误支持   | 正确 execution value 会支持包含错误方向的整句，dimension 又读取完整答案                     | numeric answer 先做 clause-level 分解；execution 只验证 result clause；方向/解释 clause 独立验证；unit/scale 只检查 result claim                                                                                                                      |
| P0-05 QASPER 改写保留旧状态      | answer contract 改写后只重新 finalization，没有重算 verifier                                | 保存 `pre_contract_verification`；清除顶层、benchmark metadata 和 bundle metadata 的 answer-dependent state；运行 post-contract verifier 并把 verified claim support 回写所有阶段                                                                     |
| P0-06 free-text support 优先     | 同时存在支持和反证时仍返回 supported                                                        | generic verifier 使用 support-only / contradiction-only / both / neither 状态表；both 返回 conflicting，最终决策不再 supported；无关事实冲突需满足共享主体/事件上下文                                                                                 |
| P0-07 contract gate 名实不符     | duplicate、conflict、round-trip 和 provenance 被压成不完整的两个指标                        | 拆分 duplicate identity、conflicting identity、canonical mismatch、atomic/locator/lineage/representation round-trip；citation provenance 使用 aliases/backrefs；legacy 汇总指标仅作为兼容投影                                                         |
| P0-08 candidate stage 指标错位   | reranker input 被当作 canonical candidate pool                                              | canonical candidate、post-fusion、reranker input、reranked、selected、generation context、execution operand、verified claim support、emitted citation 分别读取真实 stage；candidate pool 指标不再由 reranker shortlist 代替                           |

## 4. 本轮已关闭的 P1

| ID                                  | 已落实修复                                                                                                                                                                                       |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| P1-01 paired records 未接线         | 标准 summary 输出 dataset/example/route/deployed role、逐样例 metrics、error 和 timeout；没有共同逐样例记录时 paired gate 返回 missing 并失败，不退回聚合均值差                                  |
| P1-02 calculation citation 提前返回 | calculation operand citations 与额外 explanatory claim citations 做稳定 union，每类 claim 保留自己的 provenance                                                                                  |
| P1-03 verified evidence 被扁平化    | 新增 `verified_claim_support_by_claim`，值为 canonical evidence identities；finalizer 通过无歧义 alias lookup 反向解析，扁平列表只保留兼容和汇总用途                                             |
| P1-04 legacy alias 歧义             | legacy alias 使用 canonical identity multimap；一个 alias 指向多个 identities 时拒绝匹配，不再 first/last-write-wins                                                                             |
| P1-05 claim aggregation 仍为句级    | 增加 clause splitting 和 typed claim key；可拆分 contrastive compound clause，并覆盖 reported/amounted 等常见等值释义；开放域语义等价仍列为校准风险，不把规则测试写成通用语义能力结论            |
| P1-06 compact artifact 审计字段缺失 | compact stage projection 保留 runtime source、page number、figure/table、parent/neighbor/section、value、period kind、statement/scope、bbox、caption、OCR/VLM、chunk、lineage 与 representations |

## 5. 当前验证证据

| 验证                     | 结果                     |
| ------------------------ | ------------------------ |
| 最新复核项定向跨模块测试 | 92 passed                |
| `benchmark/tests`        | 528 passed，6 warnings   |
| `libs/ktem/ktem_tests`   | 1464 passed，45 warnings |
| codebase hygiene ratchet | passed；未刷新 baseline  |
| changed-files pre-commit | passed                   |
| 新 benchmark artifact    | 尚无                     |
| 新 Slurm 任务            | 未提交                   |

warnings 是现有第三方弃用/版本提示，不是本轮新增失败。单元测试证明代码不变量成立，
不证明真实 parser、模型输出、数据集分数或延迟已经达标。

## 6. 最新开放问题表

这里只保留无法由本轮静态实现和本地单元测试真实关闭的事项。

| ID                    | 优先级      | 状态                      | 根因与当前缺口                                                                                                                                    | 关闭标准                                                                                                                          |
| --------------------- | ----------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| CONTRACT-ARTIFACT-001 | P0 验证阻塞 | 待真实 artifact 验证      | 单元测试使用受控 parser/index/model shape；真实 artifact 仍可能首次暴露 identity、locator、stage 或 citation lineage 缺口                         | FinanceBench/QASPER 各 2–5 条 smoke 中 duplicate/conflict/mismatch/provenance/lineage violation 全为 0，所有 stage 可逐 atom 回溯 |
| FIN-ATOMIC-SUPPLY-011 | P0 验证阻塞 | 代码就绪，真实 PDF 未证实 | wrapped row、跨页 table continuation、局部 period/scale header 是否稳定生成 atomic cell 只能由真实解析结果证明                                    | 困难样例 required operand/dimension 全部绑定到 cell/span；缺失 requirement 时不执行；citation 覆盖全部 operands                   |
| SEMANTIC-JUDGE-020    | P1          | 待冻结人工校准集          | 尚无本轮 200 条人工标注 artifact，不能从代码推断 judge 一致率                                                                                     | 200 条校准集 coverage ≥99.5%、人工一致率 ≥90%，核心数值/方向/单位/极性冲突不得判 supported                                        |
| VERIFY-FREETEXT-028   | P1          | 待校准验证                | deterministic verifier 已覆盖 boolean、numeric、year、direction、negation 和局部 relation；开放域主体、关系、条件、作用域及复杂释义仍不是完备 NLI | 按 answer type 报 precision/recall；冻结反例中的错误主体/关系/条件/作用域不通过；每个 supported claim 均有 canonical provenance   |
| LATENCY-PAIRED-008    | P1          | 已埋点，待 artifact       | 没有同样例、同 route、同后端的本轮 paired timing artifact                                                                                         | timing coverage 100%；简单 QA 中位增幅 ≤20%，复杂 QA ≤50%                                                                         |

## 7. 下一步验证顺序

1. 先运行 FinanceBench 与 QASPER 各 2–5 条 `artifact_detail=full` smoke。
2. 逐样例检查
   `canonical candidate → post-fusion → reranker input → reranked → selected → generation context → execution operand → verified claim support → emitted citation`。
3. 任一 contract violation 非 0 时停在首次断裂阶段，不通过 reranker、MMR、prompt
   或评分权重掩盖。
4. smoke 通过后运行 QASPER 159×3 与 FinanceBench 20×4 聚焦验证。
5. 聚焦验证通过 contract gates、paired regression、semantic calibration 和 latency
   coverage 后，再决定是否运行全量 benchmark。
