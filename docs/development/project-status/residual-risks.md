# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-28

## 1. 当前结论

本轮以 `Dev` 提交 `1739828e9033ed0530676e8401a44f1d279281bb` 的复核报告为
输入，先关闭会让 artifact 失真的 P0，再处理其余静态审查项。

复核报告中的三个 P0 已完成代码修复和失败保护测试：

1. citation、calculation 和 reranker lineage 只用 atomic exact identity 做 join，
   不再用父表 alias 扩散到兄弟 cell，也不再把 source 与 page 交叉组合；
2. visual、structured 和 cross-page 不再是互斥 question type；跨页视觉问题会生成
   两个具有 modality hint 的必需 support slots；
3. `required_for_verification` 已进入 verifier，缺失 slot 或 slot evidence 没有支持
   claim 时不能返回 `supported`。

其余可由静态代码关闭的问题也已落实：multi-retriever lineage、跨模态
representations、span identity、required-slot 候选配额、score 归一化、
source-page paired metrics、headline policy、release gate 分类、boolean proposition
验证和分阶段 latency 记录。

这代表本轮复核中的**代码契约断点已经关闭**，不代表数据集能力已经通过验收。当前
仍没有使用本轮代码生成新的 QASPER/FinanceBench artifact，因此：

- 可以进入每类 2–5 条 contract smoke；
- smoke 通过后可以运行 QASPER 159×3 和 FinanceBench 20×4 聚焦验证；
- 在聚焦 artifact 证明 identity、stage、citation 和 paired regression 均通过前，
  不建议运行全量 benchmark。

本轮未改变公开 `MARA`、`MARA-cli` 或 `MARA docqa` 命令及参数，也未提交 Slurm
任务。

## 2. 根因复盘

此前多轮修复反复回退，不是因为某个 reranker 阈值不够好，而是下游继续用旧字段
重新解释上游已经声明的类型和阶段。本次复核暴露的具体形式包括：

- atomic cell 与父表共享 `evidence_id`，citation/lineage join 把 grouping alias
  误当成 exact identity；
- `(source_id, page_label)` 被拆成两个集合，产生并不存在的交叉 locator；
- visual 和 cross-page 被建模成互斥类型，导致同时需要两种能力的问题绕过多证据
  约束；
- slot 声明 `required_for_verification=True`，verifier 却只看全局文本重叠；
- dedupe 合并正文，却没有合并 dense/sparse lineage 或保留 OCR/VLM representation；
- selection 在 required evidence 进入前统一硬截断，并直接混加不同 score 空间；
- benchmark headline、stage 和 release gate 字段没有准确反映实际执行语义。

共同根因是缺少可执行的不变量：

```text
identity declaration
→ stage execution
→ projection
→ metric join
```

本轮的关闭标准不是“某个函数已修改”，而是四个位置使用同一 identity/stage contract，
且存在跨模块回归测试。

## 3. 已完成且有代码证据的修复

| 契约                        | 当前实现                                                                                                                        | 保护证据                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Atomic citation identity    | exact aliases 与 grouping aliases 分离；兄弟 cell 不共享 exact join key                                                         | sibling-cell、source-page pair、emitted citation tests |
| Calculation citations       | execution citation 保留匹配到的 canonical cell identity，同表多个 operand 不折叠                                                | calculation citation identity tests                    |
| Visual cross-page plan      | capability 独立表达 visual/multiple/distinct-page/structured；左右 slot 带 modality hint                                        | visual cross-page 与常见问法 tests                     |
| Verification slots          | verifier 检查 bound plan 的 verification-required slots 和 claim support provenance                                             | missing/unsupported verification slot tests            |
| Quality retry               | 每个 query fallback 候选先 `strip()`，空白 retrieval query 不再短路回退                                                         | whitespace retry test                                  |
| Reranker lineage            | 只接受 exact atomic identity；父表 alias 和全局 text hash 均不能制造 lineage                                                    | shared-parent/global-text lineage tests                |
| Multi-retriever RRF         | dedupe 稳定合并全部 retrieval lineage；RRF 按 `retriever_name/raw_rank` 动态建表                                                | dense+sparse lineage/RRF tests                         |
| Multimodal identity         | 同一 identity 保留 representation 列表；结构化或文本事实冲突抛 contract error                                                   | OCR/VLM conflict 与 representation union tests         |
| Span round trip             | runtime schema、coercion 和 benchmark record 均保留 `span_id`                                                                   | span round-trip test                                   |
| Candidate budget            | 在全局 cutoff 前给每个 retrieval-required slot 保留最多两个候选；按稀缺度优先，optional slot 不占 required budget               | below-cutoff quota/optional budget tests               |
| Score contract              | evidence-set relevance 使用同一 query 内的 rank normalization；临时 selection score 不污染 evidence metadata                    | incompatible score-space tests                         |
| Marginal objective          | page novelty 使用 `(source_id, page_label)`；neighbor join 使用 alias-aware identity                                            | cross-source same-page/neighbor tests                  |
| Benchmark projection        | 保留 numeric、visual、span、lineage 和 representations；未知 parser 字段进入 `extension_metadata`                               | lossless/extension metadata tests                      |
| Stage metrics               | 新增 fused 与 execution-operand coverage；candidate@50 使用统一 ranked candidates；gold identity 可读嵌套 `identity.local_id`   | stage metric tests                                     |
| Locator metric              | headline all-gold-pages 使用 source-page pair；page-only 只保留为 legacy diagnostic                                             | paired locator tests                                   |
| Headline policy             | 有 `controller_auto` 时只统计实际部署 controller policy；fixed/CRAG 不重复进入 headline                                         | controller headline tests                              |
| Release gates               | 拆分 contract、paired regression 和 capability target；长期目标不伪装成代码 gate                                                | release gate category tests                            |
| Typed verification          | boolean 生成 proposition slot；yes/no polarity 及高重叠关系/否定冲突被检查                                                      | boolean polarity 与 relation/scope tests               |
| Finance atomic verification | quick-ratio verifier 优先读取 cell `row_label/value`，不再把 `Q2` 的 `2` 当金额；已知公式可从问题推断 finance slots             | quick-ratio regression tests                           |
| Latency segmentation        | runtime 记录 planning/retrieval/generation/retry/verification/finalization；benchmark 另记 answerability 和 answer finalization | controller/runner timing tests                         |
| Identity properties         | 多 source、kind、table、year、alias、continuation 的组合 round trip 无 collision                                                | identity property tests                                |

## 4. 当前验证证据

| 验证                   | 结果                     |
| ---------------------- | ------------------------ |
| P0/P1 定向跨模块测试   | 199 passed               |
| `libs/ktem/ktem_tests` | 1408 passed，45 warnings |
| `benchmark/tests`      | 489 passed，6 warnings   |
| 新 benchmark artifact  | 尚无                     |
| 新 Slurm 任务          | 未提交                   |

单元测试证明代码不变量成立，不证明真实 parser、runtime adapter、模型输出或数据集指标
已经达标。

## 5. 最新开放问题表

表中只保留当前无法靠本轮静态代码和本地单元测试真实关闭的事项。

| ID                    | 优先级 | 状态                      | 根因与当前缺口                                                                                                                                                   | 关闭标准                                                                                                        |
| --------------------- | ------ | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| CONTRACT-ARTIFACT-001 | P0     | 待真实 artifact 验证      | runtime parser、adapter 或模型输出仍可能破坏已通过单元测试的 identity/stage contract                                                                             | Finance/QASPER 各 2–5 条 smoke 中 candidate→emitted citation lineage 100%，contract violation=0；再完成聚焦验证 |
| FIN-ATOMIC-SUPPLY-011 | P0     | 代码就绪，真实 PDF 未证实 | schema、selection、execution 和 verifier 已支持 cell/span，但 wrapped row、局部 scale 和 period header 是否稳定产出 atom 只能由真实 parser artifact 证明         | 困难样例 operand/dimension atom 全部可回溯；缺失时不执行；execution citation 覆盖全部 operand                   |
| SEMANTIC-JUDGE-020    | P1     | 待人工校准 artifact       | semantic evaluator 契约和 gate 已存在，但仓库没有真实的冻结 200 条人工标注结果；代码不能伪造人工一致率                                                           | 冻结 200 条；coverage≥99.5%，人工一致率 ≥90%，数字/方向/单位冲突通过率为 0                                      |
| VERIFY-FREETEXT-028   | P1     | 待校准验证                | deterministic verifier 已处理 numeric、boolean、year、direction、negation 和明显 relation conflict；开放域长文本 entailment 仍依赖尚未完成的 semantic judge 校准 | 冻结集按 answer type 报 precision/recall；supported claim 全有 atomic provenance；错误主体/关系/作用域不通过    |
| LATENCY-PAIRED-008    | P1     | 已埋点，待 artifact       | 各阶段 timing 已记录，但没有本轮 route-specific paired artifact，无法声称满足延迟门槛                                                                            | timing coverage=100%；同样例 paired 报告中简单 QA 中位增幅 ≤20%，复杂 QA≤50%                                    |

## 6. 已关闭并从开放表移除的问题

以下问题已有实现与包级回归，不再重复列为开放 bug：

- citation 在同表兄弟 cell 间扩散或折叠；
- calculation citation 退化为父表 ID；
- citation source/page cross join；
- visual cross-page 绕过左右 slot；
- `required_for_verification` 未执行；
- 空白 quality retry；
- 父表 alias 造成 reranker lineage 假阳性；
- dedupe 丢失 multi-retriever lineage；
- 相同 identity 的 OCR/VLM 冲突被静默吞掉；
- span identity 在 runtime→benchmark 丢失；
- required evidence 在统一 80/30 cutoff 后无法恢复；
- optional slot 提前消耗 required page budget；
- selection 直接混加不同 score 空间；
- marginal objective 使用 page-only locator 或 raw neighbor ID；
- fused/execution stage coverage、paired page metric 和嵌套 gold identity 缺失；
- controller/fixed/CRAG 重复进入 headline；
- contract、paired regression 和长期目标混在同一 release gate；
- QASPER boolean 没有 proposition/polarity contract；
- generation、verification、finalization 没有独立 timing；
- identity 只有固定单例测试，没有组合不变量测试。

这些关闭结论只针对代码契约。真实数据集结果统一由开放问题表中的 artifact 验证关闭，
不能用历史 artifact 或指标换名作为证据。

## 7. 下一步顺序

1. 生成 FinanceBench 和 QASPER 各 2–5 条 smoke artifact。
2. 逐条核对
   `candidate → fused → reranked → selected → generation_context → execution_operand → verified_claim_support → emitted_citation`。
3. 任一 identity、slot、stage 或 citation contract violation 非 0，立即停在首次断裂
   阶段修复，不调 reranker/MMR/prompt 掩盖。
4. smoke 通过后运行 QASPER 159×3 与 FinanceBench 20×4。
5. 聚焦验证通过 contract gates、paired regression 和 latency coverage 后，再决定是否
   运行全量 benchmark。
