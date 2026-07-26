# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-26
最新聚焦 artifact 代码：`99e55b0`
对照 artifact 代码：QASPER v18 / FinanceBench v17 为 `ec5d586`
当前结论：**仍有 P0 阻塞项，不应重跑全量 benchmark。**

## 1. 文档边界与事实纪律

本文档只记录最新完成的聚焦验证仍能复现、并且能够由 artifact
或当前代码路径解释的问题。旧问题在最新运行中已经关闭的，移到“已关闭问题”；
没有证据支持的推测直接删除，不把推测包装成根因。

本轮事实来源：

以下聚焦 artifact 已在本轮完成逐样本分析并把指标、失败样本和根因转录到本文；
2026-07-26 按存储清理要求删除其本地目录。路径仅保留为历史运行身份，不再表示文件
当前可访问。scratch 当前只保留
`final_thesis_benchmark_statistical_20260705_fullsystem_postfix` 全量结果。

- QASPER v19，159/159，无 execution error/timeout：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-qasper-typed-v19-semantic-proposition-identity-l40s/01_core_text/20260726_161424_residual-qasper-typed-v19-semantic-proposition-identity-l40s-9945264`
- QASPER v18 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-qasper-typed-v18-proposition-provenance-l40s/01_core_text/20260726_134856_residual-qasper-typed-v18-proposition-provenance-l40s-9944162`
- FinanceBench v18，20 × 4 = 80/80，无 execution error/timeout：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-finance-v18-semantic-binding-lineage-l40s/outputs/20260726_172006_residual-finance-v18-semantic-binding-lineage-l40s`
- FinanceBench v17 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/04_residual_validation/residual-finance-v17-semantic-scale-provenance-l40s/outputs/20260726_145113_residual-finance-v17-semantic-scale-provenance-l40s`

QASPER 和 FinanceBench 的新旧运行使用相同冻结样本、manifest、模型和服务脚本，
但代码提交不同。Finance 每轮还使用独立新建的运行索引，因此回答、page hit 等结果可以
比较，但不能把所有候选集合变化都单独归因于某一行代码。

## 2. 最新事实基线

### 2.1 QASPER v18 → v19

| 指标                |     v18 |     v19 | 结论          |
| ------------------- | ------: | ------: | ------------- |
| token/native F1     |  61.93% |  64.67% | +2.74 pp      |
| semantic F1         |  58.49% |  62.26% | +3.77 pp      |
| boolean exact       |   45/99 |   51/99 | +6            |
| boolean semantic F1 |  45.45% |  51.52% | +6.07 pp      |
| unanswerable exact  |   48/60 |   48/60 | 无变化        |
| typed 结构合法率    | 155/159 | 155/159 | 仍未达到 100% |

23 条答案改变；native 为 14 胜、9 负，semantic 为 14 胜、8 负。v10 对
boolean abstention 的恢复有效：9 条恢复中 8 条正确；但是 14 次直接 polarity
覆盖只有 6 次修正正确，反而把 8 条原本正确的 primary answer 改错。

已复核的错误包括：

- “Do they use attention?”：证据明确说明使用 attention，却被 `no_complete`
  改成 `no`。
- “Is the system tested on low-resource languages?”：证据说明 Hindi 是
  low-resource，仍被改成 `no`。
- “Do the hashtag and SemEval datasets contain only English data?”：引用明确包含
  English datasets，仍被改成 `no`。
- 4 条 gold unanswerable 仍输出 `99.53%`、`700`、特征列表等自由文本。
- 1 条 verifier 输出生成超长未闭合 quote；一次 JSON repair 后仍解析失败。

### 2.2 FinanceBench v17 → v18

| 指标                      |    v17 |    v18 | 结论      |
| ------------------------- | -----: | -----: | --------- |
| token F1                  | 14.07% | 12.16% | -1.91 pp  |
| native numeric            | 11.25% |  7.50% | -3.75 pp  |
| semantic F1               | 33.75% | 23.00% | -10.75 pp |
| page hit                  | 45.00% | 33.75% | -11.25 pp |
| Reranked Recall@10        | 37.50% | 32.50% | -5.00 pp  |
| all-gold-pages hit        | 27.50% | 21.25% | -6.25 pp  |
| slot coverage             | 87.78% | 75.56% | -12.22 pp |
| all-operands              | 37.50% | 37.50% | 无变化    |
| execution accuracy        | 37.50% | 37.50% | 无变化    |
| unit accuracy             | 83.33% | 83.33% | 无变化    |
| false abstention          | 16.25% | 17.50% | 变差      |
| reranker lineage coverage | 98.86% |   100% | 已修复    |

配对结果为 native 0 胜/3 负、semantic 3 胜/10 负、page hit 0 胜/9 负。
24 条适用计算问题仍只有 9 条执行成功，说明本轮没有提高计算覆盖，回退主要发生在
检索候选、证据选择、slot 绑定和生成之前。

关键样本：

- `00882`：最终 page 2 证据包含两个 4.2B，计算器也抽取并验证了两个 operand；
  但早期 QueryPlan 的 slot 仍为 `missing`，verifier 在重新做语义匹配之前就返回
  `required_slot_missing`。当前 matcher 对该真实证据可正常命中，所以此前
  “modifier 导致短语不连续”的解释不成立，已经删除。
- `10285`：最终 page 52 已含 Boeing 2018 PP&E 12,645，operand/value/period
  均正确，但同样被早期 `slot.status=missing` 否决。
- `03531`：虽然抽取出 325，但对应 page 69 是衍生品表，不含 total current
  assets；这里的拒绝是正确的，不能因为修 `00882` 而放宽。
- `10499`：cost-of-products-sold 候选存在，但 inventory slot 被现金流量表中的
  “Changes in current assets / Inventories”错误填满。它是库存变动，不是资产负债表
  的期末库存余额；slot `filled` 没有表达 stock/flow/change 语义。
- `00563`：问题要求比较 AMD 各 segment 在 FY21→FY22 的比例增幅，但
  QueryPlan 只生成一个宽泛 `support:cross_page` slot；检索 query 没有展开为
  segment net sales table，最终在没有完整分部数值时把 Data Center 错答成 Client。
- `01928`：v17 候选有 8 条并包含 gold page 11，v18 只有 3 条 page 1/2/3，
  三个 QA route 都从正确的 2,018 million 退成 unanswerable。这是实际候选回退。
- `04854`：仍正确计算 3,215.4 million，但使用 page 17/37 的等价表格而没有使用
  标注 page 52，答案能力未退化，严格 page locator 指标退化。
- `04980`：程序正确得到 4.625B，历史 native 仍按 gold 4.60 判错；这是独立评测
  精度问题，不能通过修改旧 native 定义解决。

原始 `predicted_answer` 有 48/80 为完整重复两次，但 finalizer 已在
`answer_for_user` 和 `answer_for_scoring` 中清除，最终重复率为 0。这是仍被修复层
吸收的生成债务，不是当前用户可见 P0。

## 3. 回退反思

本轮回退不是一个阈值问题，而是修复过程违反了三条工程不变量。

1. **让同一个不稳定 judge 既判定又直接改写答案。**
   v10 新增 complete/partial 标签后，只要 quote 在 evidence 中，就完全相信模型的
   `yes_complete/no_complete`，绕过原有 relation 检查。模型对 evidence 句中的局部
   否定和 question 的总体极性发生混淆，导致 8 次“正确 primary → 错误 flip”。

2. **删除了 exact ID 限制，却保留了旧状态的否决权。**
   Finance 修复只移除了 `slot.evidence_ids` 授权集合，但
   `_verify_required_slots` 仍在看到 `status=missing` 时提前退出。第二轮检索和最终
   evidence 已经改变，旧状态却没有在最终证据上重新绑定，所以问题只是从
   “exact ID 不一致”移动成“stale status 否决”。

3. **把代码修复验证和索引重建同时改变。**
   v17 在 `ec5d586` 上运行，v18 在 `99e55b0` 上运行，并分别建立隔离索引。
   `01928` 的输入候选集合已经不同；此前没有先锁定候选集合或索引指纹，就无法区分
   matcher 修改、索引构建漂移和 reranker 输入漂移。这使得局部测试通过后仍可能出现
   全局 page-hit 回退。

此前多轮没有根本修复，是因为保护测试使用了简化构造：

- `00882` 测试把 slot 预设为 `filled`，没有复现 artifact 中
  “旧 status missing、最终证据正确”的状态。
- QASPER 测试只验证模型返回的单个 verdict 如何映射，没有验证
  “primary 原本正确时禁止单 judge 直接覆盖”的系统级不变量。
- Finance table 测试验证词是否出现，却没有区分 balance、flow 和 change。
- 聚焦运行只看目标样本是否改善，没有设置 paired non-regression gate，因此
  `01928`、`00563` 等非目标样本回退没有阻止本轮实现进入下一阶段。

## 4. 成熟 benchmark 如何规避同类问题

这里参考的是官方论文、官方代码和公开评测实现中的问题拆分方法，不是寻找可直接复制的
“万能修复”。

### 4.1 QASPER：统一生成，答案和证据分别监督、分别评分

[QASPER 论文](https://aclanthology.org/2021.naacl-main.365/)和
[官方 LED baseline](https://github.com/allenai/qasper-led-baseline)把 extractive、
abstractive、yes/no 和 unanswerable 都编码成一个生成任务；同时用独立 evidence
classification head 选择 paragraph。Answer-F1 对多个参考答案取 max，Evidence-F1
对多个参考 evidence 取 max。官方实现没有再调用第二个同源 judge 覆盖已生成 polarity。

这对 MARA 的启示是：

- 生成器与 verifier 可以共享 evidence，但 verifier 不应拥有无条件改写答案的权力。
- answer quality 与 evidence selection 必须分别报告，不能因 evidence miss 直接把一个
  已有支持的答案翻转。
- 官方完整 QASPER 允许自由文本；本项目的 `qasper_typed_v2` 是只保留 boolean 与
  unanswerable 的聚焦派生集，因此三标签出口只能作用于该 suite，不能扩散到完整
  QASPER。
- 官方数据中少量 `no` 可以由整篇论文缺少某项内容支持，所以“局部 retrieved excerpt
  没提到”仍不能当作 `no`；只有完整 paper scope 或明确否定才能支持。

### 4.2 FinanceBench：用 oracle 与 retrieval 配置分离瓶颈

[FinanceBench 官方仓库](https://github.com/patronus-ai/financebench)提供 answer、
justification、evidence text 和 evidence full page；论文使用人工正确性评审，并把
closed-book、vector store、long-context 和 oracle evidence 分开。其
[官方论文](https://arxiv.org/abs/2311.11944)中 GPT-4-Turbo 的 oracle evidence
成功率为 85%，而 retrieval 配置错误或拒答 81%，直接证明“生成能力”和“页面召回”
必须分开诊断。官方 notebook 的 1024 字符 chunk、30 overlap 和普通 vector store
只是基线，并没有解决表格身份、statement semantics 或多步程序。

这要求 MARA 保留 direct/oracle 诊断 route，并把 document、page、candidate、rerank、
slot、execution 分阶段报告；不能只看最终答案后猜测 retrieval 是否失败。

### 4.3 FinQA、TAT-QA、MultiHiertt：显式事实、受限程序和表格结构

- [FinQA 官方实现](https://github.com/czyssrs/FinQA)把 `gold_inds`、reasoning
  program 和 execution answer 分开，先检索 supporting facts，再生成白名单操作符
  程序，同时报告 program accuracy 与 execution accuracy。官方还曾因 table-row
  格式不一致造成 label leak 而下调结果，说明评测格式和输入不变量必须冻结。
- [TAT-QA](https://aclanthology.org/2021.acl-long.254/)先标注答案相关 table
  cell/text span，再分别预测 operator、number order 和 scale；它不让语言模型直接
  从整页自由生成数值。其错误分析也把 wrong evidence、wrong calculation 和 scale
  error 分开。
- [MultiHiertt 官方实现](https://github.com/psunlpgroup/MultiHiertt)为 table cell
  保留 hierarchy-aware description，并显式标注 text/table supporting facts；
  pipeline 先做 fact retrieval 与 question-type classification，再进入 program
  generation 或 span selection。

对应到 MARA，核心不是增加 prompt，而是让 operand 带 cell/row/period/statement
身份，让 operator、order、scale 和 execution 可独立验证；多表问题还需要保留父子
表头和 continuation。

### 4.4 固定索引与 page-level oracle

2026 年针对 FinanceBench 的
[retrieval gap 研究](https://proceedings.mlr.press/v318/kobeissi26a.html)
在同一个 shared multi-document index 上分别测 document、page 和 chunk discovery，
并发现 page-level retrieval 仍显著落后于 oracle；domain-specific page scorer 能改善
该瓶颈。这支持 MARA 的 paired 运行必须复用相同索引/候选输入，并增加 page-level
diagnostic，而不是在重建索引的同时判断某一代码改动是否有效。

## 5. 开放问题与关闭标准

| ID                    | 优先级 | 状态                       | 根因                                                                                                                           | 关闭标准                                                                                                         |
| --------------------- | ------ | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| QASPER-POLARITY-003   | P0     | 已实现，待聚焦验证         | 单一 verifier 的 conflicting verdict 可直接覆盖非 abstain primary；complete 只验证 quote grounded，不验证 question proposition | 非 abstain primary 不被单 judge 直接改写；冻结 99 条 boolean 无 paired regression，boolean exact/semantic 净提升 |
| QASPER-TASK-003       | P0     | 已实现，待聚焦验证         | typed suite 的生成 prompt 和最终出口仍允许自由文本；结构约束只存在于评分器                                                     | typed 输出合法率 100%；4 条当前结构失败转为 canonical `unanswerable`；parser coverage ≥99.5%                     |
| FIN-SLOT-STATE-003    | P0     | 已实现，待聚焦验证         | 早期 slot status 被当作最终授权，未在最终 selected evidence 上重新语义绑定                                                     | `00882`、`10285` 通过；`03531` 错 metric 继续失败；verified slot 只由最终 evidence 决定                          |
| FIN-TABLE-CONTEXT-003 | P0     | 已实现，待聚焦验证         | table binding 没有区分 balance/stock、cash-flow/change 和 income/flow                                                          | `10499` 不再用 inventory change 填库存余额；正确 balance-sheet inventory 可绑定                                  |
| FIN-RETRIEVAL-002     | P0     | 已实现检索计划，待聚焦验证 | Finance focus query 不覆盖 adjusted non-GAAP EBITDA 和 segment proportional increase，完整表格证据没有成为生成前置条件         | `01928` gold page 回到候选和 rerank；`00563` 检索到含 FY21/FY22 segment sales 的表；聚焦运行 page hit 不低于 v17 |
| FIN-COMPARISON-001    | P0     | 开放                       | segment argmax 问题没有实体 × 时期 slots 或确定性 comparison plan，依赖 LLM 从不完整表格直接生成                               | `00563` 为各非排除 segment 绑定 FY21/FY22 值并用 Decimal 计算 proportional change，输出 Data Center              |
| BENCH-PAIRED-002      | P0     | 部分落实                   | 目标测试和聚焦运行缺少全样本 paired non-regression gate；历史运行的索引身份未进入可比性审计                                    | 使用同一不可变索引快照完成 A/B；artifact 报告 answer/page/candidate wins/losses；输入契约不一致时禁止因果结论    |
| RERANK-TRACE-001      | P1     | 部分落实                   | trace 已记录 post-fusion 输入/输出，但 backend 仍为 `not_recorded`                                                             | 记录实际 backend、模型、执行状态、输入/输出数；未执行时明确说明                                                  |
| EVAL-LOCATOR-002      | P1     | 开放                       | strict gold page 与等价事实页没有分离，`04854` 类正确答案被记为 page miss                                                      | 保留 strict page hit；新增 equivalent-evidence diagnostic，不修改历史指标                                        |
| FIN-EVAL-001          | P1     | 开放                       | 旧 native numeric 没有数据集精度/舍入语义                                                                                      | 保留旧 native；新增 precision-aware diagnostic 并单独报告                                                        |
| FIN-UNIT-002          | P1     | 开放                       | unit/scale 覆盖仍不足                                                                                                          | 聚焦运行 unit accuracy ≥98%                                                                                      |
| RELEASE-001           | P1     | 外部阻塞                   | 上述 P0 未关闭                                                                                                                 | P0 聚焦验证全部通过后才允许一次全量重跑                                                                          |

## 6. 本轮落实方案

### 6.1 QASPER：把 verifier 从“答案改写器”降为“受约束裁决器”

- 对已有 `yes/no` primary，verifier 可以确认或记录冲突，但一个同源 judge 不能直接
  改写 polarity；冲突时保留 primary，并记录 `polarity_conflict_preserved`。
- 只有 primary 为 `unanswerable` 时，grounded complete proposition 才能恢复为
  `yes/no`。v19 中该路径 9 条有 8 条正确，应保留。
- complete verdict 仍必须有 grounded quote；partial/insufficient 不得恢复答案。
- typed QASPER prompt 明确只允许 `yes/no/unanswerable`。最终出口按 suite contract
  再做一次 canonicalization，不读取单条 gold 决定答案。
- 为 8 条错误 flip 的模式增加回归：局部否定、限定范围否定、正向 relation 证据均
  不得覆盖原 primary。

### 6.2 Finance：最终证据重新绑定，而不是信任旧 slot 状态

- `_verify_required_slots` 必须忽略早期 `status` 的授权含义；每个 required slot
  都在最终 selected evidence 上重新检查 evidence/cell、metric、period、value、
  unit、scale、currency 和 entity。
- `status` 和旧 evidence IDs 只保留为 retrieval trace；最终
  `verified_required_slot_ids` 才是计算授权事实。
- 增加真实 `00882`/`10285` 形状的测试：slot 是 missing，但最终证据完整时必须通过；
  `03531` 的错表仍必须失败。

### 6.3 Finance：引入 statement/value semantics

- 对 inventory balance，拒绝把 cash-flow statement 中
  `Changes in current assets and liabilities / Inventories` 当作库存余额。
- metric matcher 先做 alias，再检查 statement context；表格 cell 的 row、period、
  statement kind 必须同时成立。
- 先为 inventory stock/change 建立明确规则；其他 metric 不做无证据的泛化。

### 6.4 Finance：补足检索计划而不是继续扩大 top-k

- adjusted/non-GAAP EBITDA 问题增加 `Reconciliation of Non-GAAP Measures`、
  `Adjusted EBITDA`、`Twelve Months Ended` 检索 focus，并生成 metric+period
  support slot。
- segment proportional increase/decrease 问题展开为 reporting segment、
  net sales/revenue、两个时期的 support slots；支持 `FY21/FY22` 归一化。
- retrieval adequacy 必须同时看到 segment 表和 sales/revenue 字段，否则触发第二轮，
  不能让宽泛公司介绍页直接进入生成。
- segment argmax 的完整确定性执行器单独实现：先从同一表格 hierarchy 中发现候选
  entity，再为每个 entity 建立两个 period cell 绑定；排除问题点名的 entity 后，用
  `Decimal` 计算每个实体的 proportional change 并执行确定性 argmax。
- comparison verifier 必须确认所有被比较实体使用同一 metric、statement、currency、
  scale 和时期；任一实体缺值时只能定向补检索或明确缺证据，不能让 LLM 猜 argmax。
  在这条链完成前，不得把“检索到表格”声称为 `FIN-COMPARISON-001` 已关闭。

### 6.5 防止再次回退

- 保护测试必须直接使用 artifact 中的状态形状，不把 `missing` 手工改成 `filled`。
- 每个实现阶段只改变一个不变量；本地测试通过后先跑同一冻结小样本的 paired
  validation，再跑 159/80 聚焦集。
- provenance 将实现身份 `contract_hash` 与成对输入身份 `paired_input_hash` 分开：
  前者包含 git，后者只包含 manifest、语义配置、非 endpoint 模型契约和冻结索引身份。
  允许 A/B 使用不同代码，但缺少索引身份或 paired input 不一致时，release gate 必须
  直接拒绝比较；索引身份只接受 `sha256:<64 位十六进制摘要>`。
- paired 报告必须列出全样本 wins/losses 和目标外回退；任何 native、semantic 或
  page-hit 的显著净回退都阻止全量重跑。
- 冻结索引身份必须来自不可变快照的内容 manifest/digest，不能用目录路径或 job ID
  伪造。作业脚本尚未实现“构建一次、只读复用”的快照制备，因此当前只能关闭比较
  gate 的代码缺口，不能关闭 `BENCH-PAIRED-002`。

## 7. 本轮验证要求

实施顺序固定为：

1. 先加入上述 artifact-derived failing tests。
2. 实现 QASPER conflict-preservation、typed contract、Finance final rebind、
   stock/change context、retrieval focus/support slots。
3. 运行相关 benchmark tests 和 `libs/ktem/ktem_tests` 聚焦测试。
4. 运行完整 `benchmark/tests`、相关 DocQA package gate、codebase hygiene 和
   changed-files pre-commit；不得刷新 hygiene baseline。
5. 只更新本节的实际测试结果。没有真实聚焦 artifact 前，P0 状态只能是
   “已实现，待聚焦验证”，不能标记关闭。

本轮已实际落实：

- QASPER 的非 abstain `yes/no` primary 在 verifier polarity 冲突时保持原答案，
  trace 记录 `polarity_conflict_preserved`；`unanswerable` 的 grounded recovery
  路径保留。
- `qasper_typed_v2` 的普通 prompt、gold-answer prompt 和 finalizer 都只允许
  `yes/no/unanswerable`；完整 QASPER 的 extractive/abstractive 行为不变。
- Finance required slot 不再读取早期 `status` 作为计算授权，而是在最终 selected
  evidence 上重新绑定 operand；真实 `missing + final evidence correct` 形状已有回归。
- inventory matcher 同时检查 metric 与 statement context，拒绝现金流量表
  `Changes in current assets and liabilities` 的 inventory change，仍接受资产负债表
  inventory balance。
- adjusted/non-GAAP EBITDA 增加 metric alias、period support slot 和 reconciliation
  retrieval focus；segment proportional change 增加 `FY21/FY22` 归一化、两个时期
  net-sales support slots、segment table focus 和 retrieval adequacy 门槛。
- run provenance 新增 `paired_input_hash` 和显式 index contract；release gate 允许
  git commit 不同，但会拒绝缺少索引身份或 paired input 不一致的 A/B。
- paired report helper 可按 dataset/example/route 对齐记录，对包括嵌套诊断字段在内
  的任意数值 metric 输出逐样本 delta 和 route 级 wins/losses/ties。

本轮本地验证：

- artifact-derived 聚焦回归：122 passed。
- `benchmark/tests`：455 passed。
- `libs/ktem/ktem_tests`：1334 passed。
- codebase hygiene ratchet：通过，未刷新 hygiene baseline。
- changed-files pre-commit：全部通过。
- storage preflight：`.venv`、UV/HF/cache/runtime 均位于 fastscratch；fastscratch
  为 135.8 GiB、441453/500000 files，scratch 清理后为 88.42 GiB、
  280616/300000 files；仓库根目录不存在 `data/`、`datasets/`、`outputs/`。

公开影响仅限 benchmark QASPER typed-suite 内部契约和共享 DocQA 的 Finance
query/evidence/calculation 语义；`MARA`、`MARA-cli`、已有 CLI 参数和持久化格式未变。

本轮不自动提交 Slurm 任务。代码和本地验证完成后，下一次集群验证仍应是
QASPER 159 条与 FinanceBench 20 × 4。QASPER/Finance 行为修复可以先验证；若要把
A/B 差异归因于代码，必须先完成不可变索引快照制备并满足 paired non-regression gate。

## 8. 已关闭问题

- **QASPER verifier 未执行：** v18/v19 已覆盖 99/99 boolean。
- **QASPER v10 abstention 恢复无效：** v19 的 9 条恢复中 8 条正确；剩余问题是
  polarity 覆盖策略，不再重复记录为“分支未工作”。
- **Finance exact evidence ID 授权：** 代码已移除初轮 ID membership 限制；当前
  剩余问题是 stale slot status，已独立记录为 `FIN-SLOT-STATE-003`。
- **RERANK-LINEAGE-002：** v18 lineage coverage 100%，reranked IDs 均属于声明的
  post-fusion candidate input。
- **REPRO endpoint topology：** v18 artifact 已记录 text LLM、VLM、retrieval、
  colvision endpoint；索引可比性是新的独立问题 `BENCH-PAIRED-002`。
- **Finance 跨证据计算能力缺失：** `04854`、`03031` 等已证明共享执行器可以跨证据
  绑定和执行；当前瓶颈是覆盖率和语义绑定。
- **Finance cell accuracy 全局错误：** v17/v18 聚焦样本均为 100%；`10499` 属于
  statement/metric 语义问题，不再误记为 cell locator 问题。
- **Finance 结果重复为用户可见错误：** v18 finalizer 已把 48 个原始重复答案清理为
  final duplicate rate 0；生成层债务保留为观察项，但不再作为发布 P0。
