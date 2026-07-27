# MARA Benchmark 剩余风险与修复状态

最后更新：2026-07-27

当前代码基线：`6bff37fa27d171f7c81d5e7cb23bf3a7fb9d74fd`

发布结论：**QASPER v24 和 FinanceBench v22 聚焦任务均完整结束，但没有通过发布
验收。当前禁止直接重跑全量 benchmark。下一轮只修复可由 artifact 证明的证据
身份、原子 cell/span、单位/期间和 citation backref 断层，并重新运行 FinanceBench
20×4 聚焦验证。**

## 1. 文档范围与事实来源

本文只记录最新 artifact 中仍可复现的问题。问题必须同时具备：

1. artifact、预测或 trace 证据；
2. 可定位的失效不变量；
3. 不依赖 gold answer 特判的通用修复；
4. 可自动验证的关闭标准。

已解决问题从开放表移除。未经过新 artifact 验证的代码改动只能标记为“已实现，
待验证”，不能标记为关闭。

本次判断读取：

- QASPER v24，159 个样本 × 3 个 route，477/477 可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_evidence_invariants/qasper-typed-v24-evidence-invariants-l40s/01_core_text/20260727_134621_qasper-typed-v24-evidence-invariants-l40s-9962978`
- QASPER v23 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_root_invariants/qasper-typed-v23-root-invariants-l40s/01_core_text/20260727_024457_qasper-typed-v23-root-invariants-l40s-9953940`
- QASPER v22 行为基线：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/qasper-typed-v22-verifier-budget-l40s/01_core_text/20260726_230904_qasper-typed-v22-verifier-budget-l40s-9952461`
- FinanceBench v22，20 个样本 × 4 个 route，80/80 可用：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_evidence_invariants/finance-v22-evidence-invariants-l40s/outputs/20260727_195210_finance-v22-evidence-invariants-l40s`
- FinanceBench v21 对照：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260727_root_invariants/finance-v21-root-invariants-l40s/outputs/20260727_031107_finance-v21-root-invariants-l40s`
- FinanceBench v20 行为基线：
  `/mnt/scratch/users/tbczhang/outputs/MARA/focused_validation_20260726_eval_invariants/finance-v20-table-identity-segment-l40s/outputs/20260727_000149_finance-v20-table-identity-segment-l40s`

v24/v22 的 `run_provenance.index_contract` 分别为
`sha256:137ff3fef097e857045768fe581b6d935d2ff70e684efd985ecabbbed790bd0a`
和
`sha256:fcefbde96736c1659212d8770c64723e3eed9d4eece697612fea67193c20c35e`。
旧 QASPER v22 和 FinanceBench v20 没有索引 digest，因此当前差异是固定 manifest、
样本和模型配置下的行为对照，不是严格冻结索引的 paired A/B。

## 2. 最新结果

### 2.1 QASPER v24

| 指标 | v22 | v23 | v24 | v24 对 v22 |
| --- | ---: | ---: | ---: | ---: |
| native/token F1 | 67.55% | 64.81% | 66.83% | -0.72 pp |
| semantic F1 | 64.57% | 60.59% | 63.73% | -0.84 pp |
| false abstention | 1.68% | 1.68% | 1.68% | 持平 |
| generation 中位延迟 | 2.19 s | 4.77 s | 5.45 s | +149% |

Boolean exact：

| Route | v22 | v23 | v24 |
| --- | ---: | ---: | ---: |
| text_rag | 50/99 | 43/99 | 52/99 |
| controller_auto | 51/99 | 45/99 | 48/99 |
| crag_guarded | 51/99 | 45/99 | 48/99 |
| 合计 | 152/297 | 133/297 | 148/297 |

v24 相比 v23 有 29 个改善、14 个退化，证明 v12 已消除上一轮大范围词法误拒。
但相比 v22 只有 11 个改善、15 个退化，仍少 4 个 boolean 正确结果。

重点样例 `b06512c17d99f9339ffdab12cedbc63501ff527e` 的三条 route 均输出
`unanswerable`，gold 为 `no`。v12 能把错误的 `yes_complete` 降级为
`insufficient_evidence`，但不能从被截断的候选中恢复正确的否定命题。text route
的 verifier 原始证据从 v23 的 5,506 字符增至 v24 的 23,373 字符，实际只使用
5,283 字符；最终保留的是 “drop-in replacement” 正向段落，而不是包含
“only requirement”的完整反证。

### 2.2 FinanceBench v22

| 指标 | v20 | v21 | v22 | v22 对 v20 |
| --- | ---: | ---: | ---: | ---: |
| token F1 | 13.40% | 12.24% | 15.77% | +2.37 pp |
| overall native | 8.75% | 3.75% | 7.50% | -1.25 pp |
| semantic F1 | 31.96% | 22.18% | 33.18% | +1.22 pp |
| page hit | 40.00% | 36.25% | 43.75% | +3.75 pp |
| Candidate Recall | 41.67% | 53.33% | 56.67% | +15.00 pp |
| Reranked Recall | 25.83% | 31.67% | 36.67% | +10.84 pp |
| slot coverage | 70.71% | 55.05% | 57.07% | -13.64 pp |
| false abstention | 17.50% | 25.00% | 26.25% | +8.75 pp |

召回和 page hit 已改善，但没有转化成 operand。60 条检索型输出中只有 17 条启用
结构扩展，pre-cap required-slot restore 只恢复 2 个候选。每条 quality route 的
9 个计算计划中只有 2 个通过验证；两个唯一成功执行样例为 `03031` 和 `04980`，
前者正确、后者错误，因此 executed-answer accuracy 只有 50%。

所有成功执行 operand 均绑定了 cell identity，说明“禁止 page 直接执行”的安全
边界有效。当前回退不是 verifier 太严格，而是上游没有稳定供给 verifier 所要求的
原子事实。

## 3. 验收标准是否过严

结论：**标准中有需要重新分层和重新测量的部分，但当前主要失败不能归因于标准过严。**

### 3.1 不允许放宽的正确性底线

以下是系统正确性而不是追分目标，任何框架都不能通过放宽这些条件发布：

- 计算 operand 必须绑定可复查的 cell 或 atomic narrative span；
- 单位、scale、currency、period 和 period kind 必须来自与事实局部一致的证据；
- 执行答案的 citation 必须来自实际参与计算的 evidence，而不是候选列表第一项；
- 冲突或缺失 operand 时必须拒绝猜测；
- 旧 `avg_f1`、native 和官方指标定义不得为了过门槛而修改。

`04980` 把 4,625 million 输出成 4,625 billion，`01928` 把季度 540 当成全年
2,018，均是数量级或期间错误。允许这类答案执行不能被解释为“让验收更现实”。

### 3.2 应调整为发布非回退标准的指标

- 发布结论以实际部署 route 为 headline。controller 和 CRAG 输出完全相同时不能
  当作三个独立系统重复平均，但各 route 仍保留为诊断。
- 小型聚焦集先检查固定样例和 stage 不变量；总体指标使用 paired 差异及置信区间，
  不要求每条诊断 route 的离散正确数完全相同。
- `page_hit` 不能单独阻塞正确的替代证据。需要同时报告 strict gold page、
  equivalent evidence 和 citation-to-executed-evidence。
- 延迟必须拆分 retrieval、generation、answerability judge、calculation 和
  finalization。当前统一 `generation_seconds` 无法证明是哪一层增加 149%，因此在
  完成分段计时前不使用单一 +20% 阈值作唯一阻塞条件；但 2.19 s 到 5.45 s 的回退
  仍是真实开放问题。

### 3.3 长期目标不作为单轮补丁的伪通过条件

全量 semantic F1、Finance native ≥20%、RAGTruth span F1 等属于系统能力目标。
它们可以阻塞正式发布，但不能要求某个只修 identity 的补丁单独达到全部长期目标。
每轮修复只需证明目标不变量成立、部署 route 不回退，并说明下一个真实瓶颈。

因此当前框架不是理论上无法满足验收，而是其 evidence IR 尚未表达验收所需的 cell、
span、单位和期间。先修表示和绑定契约比降低门槛更合理。

## 4. 当前根因

### 4.1 QASPER：冲突过滤器不是对比证据恢复器

v12 已把通用 semantic complete 与高精度 modal conflict 分开，上一轮的大范围
boolean 回退明显恢复。但 verifier 输入仍按普通相关性和字符预算组装。命题的肯定、
否定、required/optional 对照没有作为同一证据组保留。检测到冲突后系统只能
abstain，不能定向寻找相反命题。

### 4.2 Finance：PDF 视觉行没有转化为统一 cell IR

Boeing `10285` 的真实表格采用：

```text
Cash and cash equivalents
$7,637 $8,813 Short-term and other investments
927 1,179 Accounts receivable, net
```

现有 parser 只支持 `row label + values` 位于同一行，因此显式 table element
产生 0 个 cell。page 文本虽然包含正确的 12,645，但 planner 只能绑定整个 page，
最终被 atomic verifier 拒绝。该问题同样影响 `04854` 和 `10499` 的部分表格。

### 4.3 Finance：soft-wrapped narrative 破坏 atomic span

`00882` 的两个 4.2B 事实被 PDF 换行拆成 “Credit” 和下一行 “Agreement enables…”。
span parser 把每个换行当作事实边界，只产出一个有效 4.2B span，第二个事实丢失。
修复必须先恢复软换行，再按句子切分；不同事实必须保留不同稳定 span identity。

### 4.4 Finance：atomic span 被错误当作全表单位约定

`source_scale_evidence()` 当前收集同一 source 的所有 scale。v22 新增的 narrative
span 带有 `scale=billion`，于是 `04980` 的无 scale table cell 被赋值为 billion，
把 `-4625` million 执行成 `-4625` billion。atomic cell/span 的局部单位不能作为
另一 evidence 的共享 convention；共享单位只能来自表头或明确的 tabular convention。

### 4.5 Finance：statement scope 和期间绑定仍按整页关键词推断

完整 consolidated balance sheet 中只要出现 “assets held for sale”，当前整张表就
被标记为 `held_for_sale`，导致普通 inventory cell 被 required-slot 过滤。
主财务报表的 consolidated heading 应优先于某一行的 held-for-sale 描述。

`01928` 的 FY slot 又被仅包含 “Adjusted EBIT”的 full-year 页面以部分 token
覆盖错误填满，随后季度 page 的 540 进入候选。finance metric slot 必须匹配完整
metric phrase；FY 问题不得由 Adjusted EBIT 或 quarter evidence 填槽。

### 4.6 Citation 没有绑定执行 provenance

`03031` 的实际计算 cell 来自 page 30，但 finalizer 从候选列表第一项附加 page 105，
最终答案数值正确、citation 错误。deterministic calculation 的 citation 必须优先由
`calculation_execution.citation_ids` 解析到 evidence source backref。

另外，生成的 cell/span 当前把裸 `cell_id` 或 `parent_element_id` 混入
`source_backrefs`。结构身份字段不是 source locator；page/source provenance 与结构
identity 必须分开。

### 4.7 单位诊断没有测量真实换算

`04980` 的 `successful_execution_unit_accuracy` 为 1.0，但答案发生 1000 倍 scale
错误。当前指标只检查 plan 内部字段存在或一致，没有检查 operand scale 到 answer
scale 的实际换算。该指标不能用于宣称单位正确。

## 5. 开放问题表

| ID | 优先级 | 状态 | 待落实内容 | 关闭标准 |
| --- | --- | --- | --- | --- |
| QASPER-CONTRASTIVE-EVIDENCE-007 | P1 | 开放 | 按 proposition 保留肯定、否定和 modal 对比证据；冲突时定向二次检索 | `b065` 返回 `no`；部署 route boolean 不低于 v22；不增加 unsupported yes/no |
| QASPER-LATENCY-008 | P1 | 开放 | 拆分 answer generation、answerability judge 和 finalization 计时，再制定 route-specific 预算 | 分段计时 coverage 100%；能定位 v22→v24 回退来源 |
| FIN-WRAPPED-TABLE-CELL-011 | P0 | 待实现 | 解析 value-first/label-wrapped PDF 表格，生成稳定 cell | `10285` 的 PPE 2018=12645 产生 cell；`04854/10499` 目标行可生成 cell |
| FIN-NARRATIVE-SPAN-012 | P0 | 待实现 | 合并 PDF soft line wrap 后切句；同值多事实保留独立 span | `00882` 两个 4.2B 绑定两个不同 span；terminated 3.8B 不参与执行 |
| FIN-SCALE-PROVENANCE-013 | P0 | 待实现 | 禁止 cell/span 为其他 evidence 提供共享 scale；仅表头或明确 convention 可传播 | `04980` 不再输出 4,625 billion；无单位证据时拒绝执行 |
| FIN-PERIOD-SCOPE-014 | P0 | 待实现 | consolidated 主表优先；finance metric 完整短语匹配；period-kind 冲突不填槽 | `01928` 不绑定 540；`10499` inventory 绑定 consolidated balance-sheet cell |
| FIN-CITATION-BACKREF-015 | P0 | 待实现 | 结构 identity 与 source backref 分离；执行 citation 从 execution IDs 投影 | `03031` citation 指向实际 operand evidence；不存在候选首项漂移 |
| FIN-SLOT-ATOMICITY-016 | P0 | 待实现 | required slot 只由可生成匹配 cell 的 table 或 atomic span/cell 满足 | slot 标记 filled 时 verifier 可回溯对应原子事实；restore trace 非静默 |
| FIN-UNIT-METRIC-017 | P1 | 待实现 | unit metric 检查实际 scale conversion 和 answer quantity | 1000 倍错误计为 unit failure；成功执行的 unit accuracy 与人工核对一致 |
| RERANK-TRACE-001 | P1 | 开放 | 记录 upstream/local/no-rerank 的真实 score lineage | 不再以 `not_recorded` 或 shortlist 冒充 reranker |
| RELEASE-001 | P0 | 被 artifact 阻塞 | 仅提交受影响的聚焦任务；P0 未关闭前不运行全量 | 所有 P0 由新 artifact 验收，部署 route 不低于行为基线 |

## 6. 已关闭并从开放表移除

- **QASPER 通用词法二次否决：** v24 已恢复 v23 的大部分 boolean 回退；剩余问题是
  对比证据供给，不再记录为同一个 semantic gate 问题。
- **Finance segment metric：** `00563` 三条 quality route 均返回 `Data Center`。
- **page operand 直接执行：** v22 所有成功执行 operand 均绑定 cell；不得为了提高
  native 放宽该规则。
- **最终答案重复：** raw 诊断字段保留原模型输出，但 `answer_for_scoring` 和
  `answer_for_user` 已去重，final-answer duplicate rate 为 0。
- **新 artifact provenance：** v24/v22 均记录非空 index contract。
- **执行器缺失：** 执行器已存在；当前问题是其输入身份、单位和期间绑定。

## 7. 本轮实施与验证顺序

1. 先加入 wrapped table、soft-wrapped span、scale provenance、consolidated scope、
   exact finance metric 和 execution citation 的失败回归测试；
2. 单独提交保护测试和本文档；
3. 实现 parser、identity、binding 和 finalizer 修复；
4. 运行相关 `benchmark/tests`、`libs/ktem/ktem_tests`、完整两套测试、hygiene 和
   changed-files pre-commit；
5. 提交实现代码；
6. 仅重建隔离索引并提交 FinanceBench 20×4 聚焦任务，不监听至完成；
7. 新 artifact 达标后再判断是否需要 QASPER 定向修复和全量重跑。

公开 `MARA`、`MARA-cli` 和 `MARA docqa` 命令及参数保持不变。EvidenceBundle、
CalculationPlan 和 benchmark prediction 只允许增加向后兼容的诊断字段，不删除或
重命名现有字段。

## 8. 新 artifact 验收

硬正确性：

- 80/80 可用，execution error=0，index contract 非空；
- 所有成功 operand 为 cell 或 atomic span；
- 单位、period kind 和 citation 均能回溯到执行 evidence；
- `04980` 不发生 1000 倍错误，`01928` 不使用季度 540；
- 不通过放宽 page 验证或 gold 特判获得执行成功。

聚焦行为：

- `10285`、`04854`、`00882` 的正确原子 evidence 进入候选和计划；
- `10499` 的 inventory 来自 consolidated balance sheet，而不是 cash-flow change
  或 held-for-sale 子表；
- `03031` 的计算 citation 与实际 operand evidence 一致；
- `00563` 继续保持正确。

发布非回退：

- headline 采用实际部署 quality route，同时保留所有 route 诊断；
- native 和 semantic 不低于 v20 行为基线，false abstention 不高于 v20；
- 若小样本离散差异未完全恢复，必须报告 paired 样例、失败 stage 和置信区间，不能
  用 token F1 或 route 重复平均掩盖。

若新 artifact 仍不能提供原子身份，下一轮继续修 index/IR，不得通过 prompt、
expected gold value、放宽 verifier 或修改官方评分制造提升。
