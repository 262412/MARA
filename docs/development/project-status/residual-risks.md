# MARA 剩余风险与开放问题

最后更新：2026-07-26。

本文档是 MARA benchmark 未关闭问题的唯一状态表。所有结论必须能够由
已完成 artifact、当前代码或可重复 fixture 证明。以下情况都不等于问题
已经关闭：

- 任务正常退出；
- 新 trace 字段已经出现；
- verifier 成功拒绝了错误答案；
- 单元测试通过，但冻结 benchmark 验收尚未通过。

只有最终行为和对应的冻结验收门槛都通过，问题才能从开放问题表中删除。

## 一、当前结论

最近一次已完成的聚焦验证是：

```text
QASPER 159:
/mnt/scratch/users/tbczhang/outputs/MARA/
final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/
04_residual_validation/
residual-qasper-typed-v17-atomic-semantic-identity-l40s/
01_core_text/
20260726_001932_residual-qasper-typed-v17-atomic-semantic-identity-l40s-9926922

FinanceBench 20 x 4:
/mnt/scratch/users/tbczhang/outputs/MARA/
final_thesis_benchmark_statistical_20260720_repair_g_fullsystem/
04_residual_validation/
residual-finance-v16-cell-binding-identity-l40s/outputs/
20260726_011653_residual-finance-v16-cell-binding-identity-l40s
```

两个任务均以 `0:0` 退出，分别产生 159/159 和 80/80 条可用预测。这只证明
运行完成，不证明质量达标。

| 数据集 / 范围                     | 上一轮 | 最近一轮 | 结论         |
| --------------------------------- | -----: | -------: | ------------ |
| QASPER native/token F1            | 62.02% |   62.02% | 无变化       |
| QASPER semantic F1                | 58.49% |   58.49% | 无变化       |
| QASPER evidence F1                | 21.66% |   21.66% | 无变化       |
| QASPER canonical boolean exact    |  41/99 |    41/99 | 未通过       |
| Finance quality native numeric    | 13.33% |   13.33% | 未通过       |
| Finance quality semantic F1       | 29.00% |   30.11% | 小幅评分变化 |
| Finance quality token F1          | 14.68% |   13.06% | 退化         |
| Finance all-route strict page hit | 42.50% |   33.75% | 退化         |
| Finance all-gold-pages hit        | 32.50% |   18.75% | 退化         |
| Finance all-operands / execution  | 29.17% |   20.83% | 退化         |
| Finance false abstention          | 18.75% |   23.75% | 退化         |

本轮已经完成代码级修复和本地回归，但新的 QASPER 159 与 FinanceBench
20×4 artifact 尚未生成。因此当前二元结论仍是：

> P0 指标尚未关闭，禁止直接启动新的 3,540 条全量 benchmark。

以下三个已经具有闭环证据的问题已从开放表删除：

- canonical lineage 覆盖和 compact metric-input replay：最近 Finance artifact
  已证明 lineage violation 为 0，compact replay 与持久化指标一致；
- 跨 evidence-item 边界污染：精确 General Mills 生产路径 fixture 现在得到
  FY2020 capex 460.8 和 FCF 3,215.4 million；
- 自然语言页码污染：回归测试已证明 `page from` 不再产生页码 `"from"`，
  数字页码与显式 `#page:<label>` 仍保留。

## 二、为什么多轮修改仍然没有从根本上解决问题

此前的修复单位是“某个函数或某个症状”，而 benchmark 的真实不变量是：

```text
冻结问题
  -> 冻结检索输入
  -> 必需语义槽位
  -> 精确 evidence / table cell
  -> 可验证的计算或命题
  -> 最终答案
  -> 可重放指标
```

具体失误如下：

1. **把可观测性当成了能力。** canonical ID、cell ID、replay candidate 和
   verifier error 让错误更容易定位，但不会自动找回正确页面，也不会保证
   row、period、unit 和 scale 绑定正确。
2. **测试没有穿过生产边界。** 旧测试使用单个干净表格；生产路径把多个
   evidence item 用空格拍平，导致下一个 item 的文件名和页码进入上一行
   表格。局部 parser 测试通过，但最终 operand 仍然错误。
3. **修改的分支在冻结样本上没有执行。** 上一轮修改了 free-text semantic
   judge prompt，但 QASPER 159 全部走 deterministic boolean/unanswerable
   评分。159 条预测和 scoring answer 逐条完全相同，因此该修改不可能改善
   本轮结果。
4. **只报告条件成功率，没有报告覆盖率。** Finance 的确定性执行器在输入
   完整时可靠，但 24 条 numeric quality 预测中只有 5 条形成合法并执行的
   plan。只看这 5 条会掩盖 19 条根本没有到达执行器。
5. **先加强下游 verifier，后修上游 retrieval/binding。** verifier 拒绝
   无来源、错 period 或缺 scale 的 operand 是正确的，但会把过去的猜测值
   变成 abstention。安全性提高，答案质量和 false-abstention 反而退化。
6. **比较的运行没有完整不变量。** 上一轮 artifact 不能证明确切 Git
   commit、dirty state、manifest、有效配置和服务启动契约。两轮 Finance
   有 19/80 个 scoring answer 改变，不能把差异归因到某一个 patch，也不能
   据此断言模型本身“不确定”。
7. **没有核对指标实际输入。** 旧的 `Candidate Recall@50=40.83%` 实际使用
   了完整的 80 条 reranker input pool。修正后真实 top-50 是 34.17%，
   pool@80 仍为 40.83%。这一部分是口径纠正，不是模型退化。

今后的修复必须由冻结 fixture 穿过完整链路。新增字段、prompt 或 guard
如果没有在目标 subset 上执行，就不能计为修复收益。

## 三、为什么 Finance 退化得如此严重

退化由一个测量修正和三个真实行为变化共同造成：

- **测量修正：** true Candidate Recall@50 是 34.17%；旧 40.83% 现在保留为
  Candidate Pool Recall@80。该差异不能描述为检索模型退化。
- **真实排序损失：** strict page hit 从 42.50% 降至 33.75%，
  all-gold-pages hit 从 32.50% 降至 18.75%，reranked recall 从 38.33%
  降至 27.50%。进入最终上下文的答案页更少。
- **真实语义绑定损失：** all-operands/execution 从 29.17% 降至 20.83%。
  旧 parser 能产生“有 identity 但语义错误”的 cell，所以 identity 100%
  并不等于 operand 正确。
- **严格验证带来的预期 abstention：** 缺 scale、错 row、把 period 当值或
  evidence 缺失都会被拒绝，false abstention 因而从 18.75% 升至 23.75%。
  这些拒绝避免了无依据答案，但没有完成 benchmark 任务。

因此不能通过放松 verifier 恢复表面分数。需要先提高答案页召回，再保证
table boundary、qualified metric、period 和 dimension provenance 正确。

## 四、开放问题表

| ID                | 优先级 | 当前 artifact 证明的问题                                                        | 当前代码状态                                                                | 关闭门槛                                                               |
| ----------------- | ------ | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| FIN-RETRIEVAL-001 | P0     | page 33.75%、reranked 27.50%；相关文本会错误填满 operand slot                   | query expansion、严格 qualifier、typed-cell slot binding 已实现；待冻结验证 | page >=70%、all pages >=35%、answer-bearing element hit@10 >=30%       |
| FIN-DIMENSION-001 | P0     | `04980` 找到 4,625，但不能证明 million 到 billion 的换算                        | same-source scale evidence 和二次 dimension retrieval 已实现；待冻结验证    | 所有换算 operand 引用 scale evidence；unit accuracy >=98%              |
| QASPER-PROP-001   | P0     | boolean exact 41/99；20 个 boolean-shaped abstention 全部绕过 verifier          | v9 proposition path 已实现；待冻结 confusion matrix                         | structure 100%、semantic F1 >=80%，且无 gold runtime routing           |
| REPRO-001         | P1     | 已完成 artifact 缺少完整 run contract，旧波次无法做严格因果比较                 | artifact fingerprint 和 clean-tree enforcement 已实现；待新 artifact 验证   | 聚焦运行记录一致 contract hash，mismatch 被拒绝                        |
| RERANK-TRACE-001  | P1     | `reranked_evidence` 可能只是 heuristic fusion 后的前 30 条，不能证明 BGE 已执行 | 尚未修复                                                                    | trace 区分 fusion rank 与 cross-encoder rank，并记录 backend execution |
| RELEASE-001       | P1     | 数据集门槛和 G-B paired CI 尚未完成                                             | 阻塞                                                                        | 所有保护门通过，G-B >=8 points 且 CI 下界 >0                           |
| EVAL-EXTERNAL-001 | P2     | 没有完整 frozen paper-grade external evaluator artifact                         | 延后                                                                        | evaluator/version/prompt/parser/retry/cost 和完整 artifact             |
| FORMAT-001        | P2     | preview/OCR/formula/chart 的生产矩阵不完整                                      | 延后                                                                        | frozen per-format 端到端矩阵通过                                       |

## 五、FIN-RETRIEVAL-001：相关词命中不等于所需事实

### 已证明的根因

- `03531` 询问 **total current assets**，但命中 pages 64/65/41，并把
  “other current assets” 当作所需事实。
- `10285` 询问 balance sheet 上的 **net property, plant and equipment**，
  但上下文只有 cash-flow additions -1,722 和无关页面。
- `04302` 需要 2016、2017、2018 三期 COGS 与 revenue；controller/CRAG
  只选 pages 36/38/60，slot coverage 为 1/3，无法生成 plan。
- `10499` 的 slot coverage 显示 1.0，但 calculation adapter 仍没有 operand。
  这证明旧 slot status 只是词面成功，不能由 cell binding 重放。

旧实现对完整 “property, plant and equipment”、“total current assets”和
COGS/revenue percentage 的扩展不完整；slot scoring 只要 alias、period 和
任意数字共现就可标为 `filled`。错误的 `filled` 又阻止第二轮检索。

### 本轮已落实

- 对 net PP&E、total current assets、COGS/revenue 增加 statement/metric
  query expansion；
- 保留 `net`、`total` 等 qualifier，specific metric 命中时移除 generic
  alias；
- Finance operand slot 优先验证 typed financial cell 的 row semantics 和
  period；有表格但没有匹配 cell 时不得填满；
- “other current assets” 不得满足 “total current assets”，cash-flow
  “additions to PP&E” 不得满足 “net PP&E”；
- 未填满的 required slot 继续触发现有第二轮定向检索。

### 仍未关闭的原因

本地 fixture 只能证明错误 slot 不再被接受，不能证明真实 PDF 索引已经把
答案页召回到前 50/10。必须重跑冻结 FinanceBench 20×4，并同时报告
Candidate Recall@50、Pool@80、Reranked Recall@10、page/all-page hit、
typed-cell hit 和 slot coverage。

此外，`reranked_evidence` 的命名仍可能混淆 heuristic fusion 与真实
cross-encoder，作为独立的 `RERANK-TRACE-001` 保留。

## 六、FIN-DIMENSION-001：scale 是带来源的事实

### 已证明的根因

`financebench_id_04980` 的表格包含：

```text
2021 2020
Capital spending (4,625) (4,240)
```

问题要求 USD billions，但该页没有重复报告前文的 “tabular dollars are
presented in millions”。旧 plan 因此只有 -4,625 和 requested scale
`billion`，没有 operand scale；verifier 正确拒绝了换算。

General Mills 的 “In Millions, Except Per Share Data, Percentages and Ratios”
也不符合旧 regex 仅支持的 parenthesized `in ...` / `dollars in ...` 形式。

### 本轮已落实

- 识别 `In Millions, Except ...` 和
  `tabular dollars are presented in millions` 等显式 convention；
- `CalculationOperand` 新增可选 `scale_evidence_id`；
- 只允许从同一 source 中唯一、显式的 scale convention 继承 scale；
- verifier 重新检查 scale evidence 是否存在、是否同 source、是否真的支持
  scale，并把 value evidence 与 scale evidence 合并进 citation；
- 请求包含 thousand/million/billion 且首轮缺 scale 时，新增 required
  `dimension:scale` slot，第二轮只检索
  `tabular dollars unit scale convention`。

精确本地 fixture 已证明 4,625 million 可转换为 4.625 billion，且同时引用
capital-spending table 和 scale convention。

### 仍未关闭的原因

最近的 Finance artifact 早于本轮代码，尚未证明真实索引能找回 scale
convention，也尚未达到 `unit accuracy >=98%`。不同 source 或冲突 scale
必须继续保持 verification error，不能用默认 scale 兜底。

## 七、QASPER-PROP-001：执行中的 boolean 路径无法修正初始决定

### 已证明的根因

最近两轮 159 条 prediction 和 scoring answer 逐条相同。99 条 boolean 和
60 条 unanswerable 都使用 deterministic semantic scoring，因此此前修改的
free-text judge prompt 没有执行。

99 条 boolean 中：

- 23 条被 verifier confirmed，但只有 15 条匹配 annotation；
- 56 条得到 `insufficient_evidence`，继续保留初始 candidate；
- 20 条初始输出为 `unanswerable`，旧路径直接跳过 verifier，20 条均不匹配
  boolean annotation。

旧 verifier 还可能把相关命题当成完整命题，例如把 “created a dataset”
等同于 “experimented with the dataset”。quote 出现在论文中只证明
grounded，不证明 subject、relation、scope、qualifier 和 polarity 完整。

### 本轮已落实

- 使用问题句法检测 boolean-shaped question，不读取 gold answer type；
- 即使初始答案是 `unanswerable`，boolean-shaped question 也执行 polarity
  adjudicator；
- 只有 grounded quote 支持完整 relation 且给出 definite polarity 时才允许
  恢复或纠正答案；
- trace 记录 primary answer、raw verifier verdict、adjudicated polarity、
  relation terms、action 和 reason；
- 增加 “created != experimented” 等负例；
- 离线覆盖审计显示新句法规则可识别冻结集 99/99 个 boolean question，
  包括 `Overall, does ...`。该 99/99 只用于测试 detector 覆盖，运行时不读取
  annotation。

### 仍未关闭的原因

boolean verifier 是模型调用，本地 mock 不能证明实际 Qwen 输出质量。必须
重跑 QASPER 159，检查 confusion matrix、20 个旧 abstention 的去向、已有
正确 candidate 是否被误改，以及 structure/semantic/evidence 指标。

## 八、REPRO-001：旧聚焦运行不能做严格因果比较

### 已证明的根因

旧 artifact 有 benchmark config 和 backend metadata，但没有一个统一、
不可变的 fingerprint 覆盖 Git、dirty state、manifest、有效配置、模型/
服务契约和 endpoint。因此不能把波次间答案差异严格归因到代码 patch。

### 本轮已落实

每个新 summary 新增 `run_provenance`：

- Git commit 和 dirty state；
- manifest path 与 SHA-256；
- 排除 output path 等非语义字段后的有效 benchmark config；
- model/service generation contract；
- 实际 service/model endpoint。

同时记录两个 hash：

- `contract_hash`：用于跨任务配对，排除会随 Slurm job 改变的临时 endpoint，
  但包含 commit、dirty、manifest、语义配置和 service contract；
- `execution_hash`：额外包含实际 endpoint，用于重放具体执行环境。

正式 Slurm 脚本在 dirty worktree 上直接失败，除非显式设置仅供开发运行的
`MARA_ALLOW_DIRTY_BENCHMARK=1`。release gate 在 B/G 任一侧含 provenance
时强制比较 `contract_hash`，不允许静默合并 mismatch。

### 仍未关闭的原因

单元测试已证明相同输入 hash 稳定、配置变化会改变 hash、mismatch 会被
拒绝；但还没有新的真实聚焦 artifact 证明 Slurm service contract 和
run_provenance 被完整持久化。

## 九、RERANK-TRACE-001：stage 名称不能证明 cross-encoder 已执行

当前 bundle 的 `reranked_evidence` 可能是 cross-modal heuristic fusion 和
page-first ordering 后的前 30 条。仅看到该字段不能证明每个 modality 都由
配置中的 BGE cross-encoder 评分。

需要分别持久化：

- canonical candidate pool 与各 retriever rank；
- fusion/RRF rank；
- reranker backend、model、input count、output count 和 execution status；
- cross-encoder score/rank；
- coverage/MMR 选择结果。

在这些字段可重放前，报告只能称其为“post-fusion selected evidence”，不得
称为“BGE 强重排结果”。

## 十、RELEASE-001：全量发布门

新的全量 benchmark 只允许在聚焦 P0 门槛通过后运行。仍需：

1. 200 条 frozen semantic calibration 的人工一致率 ≥90%、judge coverage
   ≥99.5%；
2. QASPER 与 Finance 聚焦门槛通过；
3. ALCE、SlideVQA、MMDocRAG、RAGTruth 保护回归通过；
4. B 到 G 使用一致 `contract_hash` 做 paired evaluation；
5. G-B QA semantic F1 至少 +8 个百分点，paired 95% CI 下界 >0；
6. historical `avg_f1`、native/citation metric 和 latency budget 无退化。

## 十一、延后但真实存在的风险

### EVAL-EXTERNAL-001

仓库已有 evaluator interface 和 local judge，但没有完整 frozen
paper-grade external evaluator artifact。关闭需要固定 provider/model
version、prompt、parser、retry、budget、calibration、coverage 和 failure。

### FORMAT-001

PDF、DOCX、PPTX、XLSX、CSV、Markdown、text 已有基础
loader/index/query smoke；preview、Office conversion、OCR、复杂 slide、
spreadsheet formula、chart、citation 和最终 QA 的生产矩阵仍不完整。

## 十二、本轮落实状态与下一步

为避免下游 guard 再次掩盖上游 miss，本轮严格按以下顺序执行：

1. [x] 先增加会失败的生产路径回归：跨 item boundary、bare period、
       scale scope、strict qualifier、QASPER boolean abstention、page locator、
       run provenance。
2. [x] 保留 evidence-item boundary，强化 typed financial-cell parsing。
3. [x] 增加 same-source scale provenance 和定向 dimension retrieval。
4. [x] 增强 Finance query expansion 和 semantic slot binding。
5. [x] 修复实际执行的 QASPER boolean proposition path。
6. [x] 增加 artifact run contract 和 Slurm clean-tree enforcement。
7. [x] 完成本地门禁：
   - `benchmark/tests`: 442 passed；
   - `test_docqa_*.py` + `test_mara_*.py`: 464 passed；
   - changed-files pre-commit：通过 black、isort、flake8、mypy、codespell；
   - codebase hygiene ratchet：通过，未刷新 baseline；
   - 两个 Slurm 脚本 `bash -n`：通过。
8. [ ] 在 clean commit 上提交 QASPER 159 和 FinanceBench 20×4 聚焦验证；
       不启动全量 benchmark。

聚焦任务完成后，先比较冻结问题级 diff 和 stage metrics，再决定哪些 P0
可以关闭。不能因为新任务正常退出就删除问题。

## 十三、更新规则

- 开放表只保留尚未满足冻结验收的问题；
- 修改 Benchmark、DocQA、reporting、controller 或 Slurm 行为前先增加
  characterization/regression test；
- 不得为通过检查刷新 `scripts/codebase_hygiene_baseline.json`；
- 所有条件指标必须同时报告 coverage 和 conditional success；
- 历史指标定义不变；口径修正只能新增并明确命名；
- runtime routing、retrieval、generation、binding 和 verification 禁止读取
  gold label、gold page、gold answer type 或 gold value；
- 任一 P0 未关闭时禁止全量 benchmark。
