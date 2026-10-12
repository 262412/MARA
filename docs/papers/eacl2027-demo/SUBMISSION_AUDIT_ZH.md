# MARA：EMNLP Demo 转投 EACL 2027 Demo 的要求审核与问题清单

> 本文保留初次审核时的状态。作者已授权后续修改，最新结果与逐项处理状态见 [REVISION_STATUS_ZH.md](REVISION_STATUS_ZH.md)。初审中的“尚未执行”不代表当前仍未执行。

- 审核日期：2026-09-22（北京时间）。
- 轮次：初次转投准备审核；尚未开始修改论文、软件、实验或视频。
- 结论：**准备与问题归纳已完成；当前材料不宜原样提交 EACL。**

本次收到的是完整 LaTeX 源码包，以及作者粘贴的 1 份 area-chair meta-review 和 3 份 reviewer review。源码、表格、编译和部分公开材料可以核验；评审提到的逐样本结果、运行配置、视频全过程和安装全过程尚未重新验证。本文区分这几类证据，不把审稿人的分析直接写成已经复现的事实。

## 1. 文件、分支与审核范围

| 项目 | 已完成的准备 |
| --- | --- |
| 工作分支 | `codex/eacl-2027-demo` |
| 独立工作区 | `C:\Users\22826\.codex\worktrees\mara-eacl-2027-demo\MARA` |
| 基线 | 本地已有的 `origin/Dev`，提交 `adab3f4d8f221e3620494fab0a24ef8e5557d12a`；未执行 fetch，不据此声称是远端最新提交 |
| 原 refactor 工作区 | `D:\PythonProject\MARA`；其分支和已有未提交改动保留 |
| 论文目录 | 本文所在的 `docs/papers/eacl2027-demo/` |
| 解压源码 | [source/](source/)；10 个原始文件逐文件 SHA-256 校验一致 |
| 原包副本 | [archive/emnlp-submitted-source.zip](archive/emnlp-submitted-source.zip) |
| 来源和校验清单 | [archive/source-manifest.json](archive/source-manifest.json) |
| 检查结果 | [audit/verification.json](audit/verification.json) |

原始文件来自 `C:\Users\22826\Downloads\MARA__A_Local_First_Multimodal_Document_QA_Workbench_with_Self_RAG_Inspired_Routing.zip`，ZIP SHA-256 为：

```text
57517b15761050d80902c5cfeea6244566d67291d26a23b52e27b6b70583b3a1
```

本轮新增的是源码存档、审核文档和检查记录。论文 `.tex`、`.bib`、样式文件和图片均保持原样。构建输出放在 `audit/build/`，没有写回源码目录。没有修改 MARA/MARA-cli、DocQA、Gradio、运行配置或持久化数据，也没有重跑 benchmark。

文件和评审中的命令、说明仅作为审核材料；例如审稿人对某安装命令的描述，不是要求在当前共享环境中执行该命令。

### 1.1 评审来源的边界

曾尝试 Windows computer use 和作者指定的 Chrome 浏览器接口。前者因无法可靠识别当前网址而停止，后者在作者刷新并确认连接后仍超时。公开 OpenReview 页面未能读取；一次无登录的公开 API 请求返回 HTTP 403 `ChallengeRequiredError`，未继续处理验证。

因此，**以下 EMNLP 评审清单依据作者在本次对话中粘贴的文本，不是声称通过浏览器成功抓取了评审。** 作者提供的原始入口是 [OpenReview 讨论页](https://openreview.net/forum?id=wOGlhXRicd&noteId=p4PBoTa9Qn)。独立的最终 Decision 文本未出现在所提供材料中；可直接引用的决定性意见是 AC 的 `Recommendation: Reject`，作者亦明确说明该稿已经被拒。

## 2. EACL 2027 Demo 投稿要求审核

以核验当日的 [Demo CFP](https://2027.eacl.org/calls/demos/) 为准。Demo 是直接向 [EACL 2027 Demo OpenReview](https://openreview.net/group?id=eacl.org/EACL/2027/Demo) 投稿的独立轨道；不能把主会 ARR 的 8/4 页、双盲、答辩阶段或审稿服务安排直接套用。

### 2.1 时间与审稿方式

| 项目 | 官方要求 |
| --- | --- |
| 开放投稿 | 2026-08-18 |
| 截稿 | 2026-09-22 23:59，UTC−12 / AoE；换算为 **2026-09-23 19:59，北京时间** |
| 录用通知 | 2026-12-18 |
| Camera-ready | 2027-01-06 |
| 会议 | 2027-03-09 至 03-14 |
| 审稿 | 单盲，论文应保留作者姓名和单位；**没有 rebuttal 阶段** |
| 审稿义务 | 每篇论文指定一位作者为其他投稿承担 reviewer 工作 |

以上均来自 [Demo CFP 的日期和审稿政策](https://2027.eacl.org/calls/demos/)，不是主会的 ARR 时间表。

### 2.2 材料与合规检查

| 检查项 | 要求与当前判断 | 后续需要完成的检查 |
| --- | --- | --- |
| 三项必交材料 | 论文、视频、在线 demo 或可下载安装包，缺项会 desk reject | 将三项对应到同一系统版本和实际提交记录 |
| 论文页数 | 正文最多 6 页；参考文献、信息性附录和可选伦理/影响说明允许额外空间 | 当前 `main.tex` 为正文 6 页、参考文献 1 页、附录 2 页；不是因总共 9 页而超页。修改后重新检查 |
| PDF 和模板 | 使用官方 ACL/EACL 格式 | 两个样式文件与核验当日官方文件 SHA-256 完全一致；构建问题见 S01–S02 |
| 作者实名 | 单盲，保留作者及单位 | 三个入口的作者和标题不统一，必须确认最终名单；不能直接使用匿名入口 |
| 视频时长 | 最多 2.5 分钟 | 原稿含 YouTube 链接，但本轮未验证时长、播放权限及完整内容 |
| 视频链接 | PDF 和 OpenReview 表单都要提供 | 实名稿中已有链接；EACL 表单未填写、未核验 |
| 视频提交方式 | 可提供公开视频；不公开时可按 CFP 使用 MPEG4 补充材料 | CFP 同时要求两个位置提供视频链接；若走非公开附件方式，须核对实际表单的链接/附件用法，不能自行假定免填 |
| 可访问系统 | live demo 或可下载安装包链接，PDF 和表单都要有 | 原稿含仓库及 v0.0.40 release 链接；GitHub release 确有 `slide-app.zip` 资产，但未完成干净环境安装验证 |
| 安装路径 | 链接可访问与安装能成功是两项检查 | `mara-research-cli` 在 PyPI 和 TestPyPI 的公开 JSON 端点均返回 404，确认该包名的问题仍存在；见 R20 |
| 系统有效性证据 | 不要求完整大型实验，但完全没有效用/质量证据可能 desk reject | 原稿已有实验；核心缺口是论证、评测有效性与展示，不是“没有任何实验” |
| 内容与图示 | 需交代技术、系统设计和使用方式，并提供适当图示 | 原稿有架构图、UI 截图、算法和表格；具体不足见后文 |
| 新颖性及相关系统 | 清楚定位与既有研究和 demos 的区别 | 缺少原始 Kotaemon 对照，且“competitive”缺乏外部参照；见 R04 |
| 公开与许可 | 明确可获取方式、许可 | 原稿标明 Apache 2.0 及上游归属；审稿人认可。NOTICE 品牌遗留另见 R24 |
| 独创与多投 | 应为未发表成果；EACL 审理期间不能同时投其他归档会议、期刊或 ARR | 先前被拒本身不等于已发表；仍需作者确认没有其他在审/已发表的显著重叠版本 |
| 同轨多篇投稿 | 同一作者团队的该轨投稿之间，内容/结果不能显著重叠（CFP 给出 >25%） | 仅在存在其他 EACL Demo 投稿时核对 |
| 伦理 | 遵守 ACL 伦理政策；涉及敏感数据/任务时须实质讨论 | 补充数据流、外部后端、展示材料授权和局限；不能把 local-first 写成无条件离线保证 |
| 录用后义务 | 至少一名作者注册，现场进行 live demo，并配 poster | 后续安排，不是本轮已经完成的事项 |

本表概括 [Demo CFP](https://2027.eacl.org/calls/demos/)；PDF 尺寸、字体、行号、作者元数据和可读性另参考 [ACLPUB 格式规范](https://acl-org.github.io/ACLPUB/formatting.html) 和 [官方样式仓库](https://github.com/acl-org/acl-style-files)。

**两项容易误判的格式问题：**

- `main.tex` 的 `[preprint]` 保留作者和页码，但没有审稿行号。ACLPUB 通用审稿规范要求行号；Demo CFP 未指定具体 LaTeX option。后续应核对实际投稿说明并选用保留实名的审稿配置，不宜直接使用会匿名的入口，也不应改写官方样式文件。
- Demo CFP 没有明确照搬 ARR 的“必须独立 Limitations 节且额外免计页数”条款。本文建议实质补充局限讨论，但不把 ARR 的附加页数豁免或 desk-reject 条件当作已经核实的 Demo 专项规则。

## 3. 原评审总体判断与应保留的优点

### 3.1 评审记录

| 标识 | 身份、日期 | 评分/建议 | Confidence | 原文定位 |
| --- | --- | --- | --- | --- |
| AC | Area Chair itYW；2026-08-16，修改于 08-22 | Reject | 4 | [meta-review revisions](https://openreview.net/revisions?id=rzDTbSnPAO) |
| R1 | Reviewer eLwq；2026-08-04，修改于 08-22 | 4，Ok but not good enough | 4 | [review revisions](https://openreview.net/revisions?id=2deh65s5MF) |
| R2 | Reviewer 2P8o；2026-07-20，修改于 08-22 | 4，Ok but not good enough | 2 | [review revisions](https://openreview.net/revisions?id=nognYmvmNT) |
| R3 | Reviewer BD6i；2026-07-20，修改于 08-22 | 5，Marginally below acceptance threshold | 3 | [review revisions](https://openreview.net/revisions?id=CAKxuXiYd9) |

AC 综合认为：系统可运行，可复现材料优秀；Demo 级别的集成贡献可以辨识，但答案质量没有被证明优于固定 text RAG，路由在部分数据上几乎不工作，失败诊断没有充分进入论文，视频及安装路径也存在问题。

几位审稿人共同认可的内容应保留：

- 真实、较完整的 local-first QA 工作台及 Web/CLI 等入口，有明确潜在用户。
- 将路由、证据充分性、验证、代价和最终状态记录成可观察对象，有 Demo 价值。
- R1 报告表中数字和配对差值能从补充包复现，41 组产物与 3,540 条预测记录能够对账；这是评审核查结果，本轮没有重新复算全部记录。
- 明确承认 heuristic score/cost 未校准，以及不主张 SOTA，是可信边界。
- Apache 2.0 和 Kotaemon 上游归属得到认可；R1 也肯定已声明的 CLI 命令和测试基础。

因此，修改方向不应简单等同于“必须训练新模型”或“所有数据集必须赢”。EACL Demo 接受系统集成贡献；需要把可观察性、实际使用价值、路由能力及其成本，用一致且有效的证据呈现出来。

## 4. 全部评审问题及后续处理目标

优先级定义：**P0** 为提交前必须处理的硬要求、错误主张或关键材料可用性问题；**P1** 为支撑核心论点的实证/方法问题；**P2** 为表达与材料整理问题。这里的优先级是本次审核安排，不是新增的 EACL 官方规则。

证据状态中，“原稿已核对”指本次读了提供的源码或构建输出；“评审报告”指来自上述转录，尚未独立复算实验或重放视频。所有“处理目标”均是后续待办，本轮没有实施。

### 4.1 主张、贡献与对照

| ID / 优先级 | 问题与来源 | 证据和处理目标 |
| --- | --- | --- |
| **R01 / P0** | p.2 声称优于固定 text RAG 的 F1 与 citation recall，和 Table 2 直接矛盾。AC、R1 指出 | **原稿已核对**：`paper_body.tex:48` 与 378–389。必须删除或准确限定这一主张，并统一摘要、引言、结果与结论 |
| **R02 / P1** | 自动路由带来的核心收益未证实。AC、R1、R2、R3 共同指出 | 主表中 controller 与固定 text RAG 持平或略低，MMDocRAG 的 visual/hybrid 也无明显优势。应明确论文证明的是哪些可观察性/使用收益，哪些质量收益仍未达到；摘要中的“model”“efficient performance”也须有相应依据 |
| **R03 / P1** | 用文本数据上的近似持平论证路由能力，但这些数据几乎只走文本。AC、R1；R2 要求路由频次 | **评审报告**：ALCE-ASQA 100%、QASPER 97% 选择 `doc_text`；ALCE 的 page-image/element 100% 因成本被跳过。应呈现选择分布，区分合理保持文本与真正发生多路线选择 |
| **R04 / P1** | 缺少未修改 Kotaemon 和外部系统参照，无法隔离 MARA 增量；competitive 的比较对象不明确。AC、R1、R2、R3 | **原稿已核对**：当前数值对照是 MARA 内部路由。后续在相同模型、数据和预算条件下提供适当的 Kotaemon 对照，并通过功能/场景对照定位相关 demos；内部路由消融不能被称作外部系统比较 |

R01 的直接核对如下，单位为原表 0–100 分制：

| 数据集 | Controller F1 | Text RAG F1 | Controller citation | Text RAG citation |
| --- | ---: | ---: | ---: | ---: |
| QASPER | 21.43 | 21.44 | 89.65 | 90.91 |
| ALCE-ASQA | 25.74 | 26.68 | 95.50 | 95.50 |
| MMDocRAG | 34.60 | 35.44 | 67.99 | 68.62 |

ALCE-ASQA 的 false abstention 两者也都是 0.00%，不能当作 controller 相对 text RAG 的提升。原稿 §3.2 本身已作谨慎解释，引言却作了相反表述。

### 4.2 路由机制与执行身份

| ID / 优先级 | 问题与来源 | 证据和处理目标 |
| --- | --- | --- |
| **R05 / P1** | 路由规则、评分公式、权重、阈值、充分性检查、verification 和切换条件不够具体。AC、R2 | **原稿已核对**：§2.2 与 Algorithm 1 主要是过程描述。后续写出关键规则/参数及默认配置，使读者能判断为什么选某路线；明确这些是未校准 proxy，不能当成实际正确率、时间或费用 |
| **R06 / P1** | Algorithm 1 给人默认会失败恢复的印象，实际 retry 受严格条件限制。R1 | **评审报告**：retrieval retry 只在 `thorough` 且检索完全为空时可达，默认 automatic 配置不触发。后续核对提交版本代码，分别交代默认模式、严格模式、空检索和答案不受支持的处理，不以概括性伪代码覆盖不同语义 |
| **R07 / P1** | 同一 page-image family/trace route 掩盖了生成后端的不同。R1、R2 | **评审报告**：controller 配置只有文本生成器；MMDocRAG 中 16 例选到 page-image family，但全部 120 条 controller 预测仍用 Qwen3-8B。Table 1 应分别列出 retrieval modality、generator、实际 VLM 使用及 fallback 状态，不能把视觉检索等同于 VLM 生成 |
| **R08 / P1** | RAGTruth 大量流向不成熟 graph route，是可诊断但未解释的失败。AC、R1 | **评审报告**：214/300 例走 global-graph，平均 F1 0.196；83 例走 text，F1 0.278。应复查 scorer、allowed routes、graph readiness，并解释其代价；214+83 只覆盖 297 例，剩余 3 例也需对账 |
| **R09 / P1** | SlideVQA 的“不同生成路线相同质量”可能来自评测不观察生成答案。AC、R1 | **评审报告**：两路线 120/120 例在 F1、EM、native、两种 citation recall 和 page hit 上完全相同，win/loss/tie 为 0/0/120；F1 有 25 个不同取值，生成平均延迟却为 4.61s/2.55s。需追踪 evaluator 实际输入、预测 answer 与 evidence-only fallback，确定是否仅在量检索结果；原因尚不能仅凭相同分数定论 |

R09 必须区分“审稿人据记录推断评分由检索决定”和“已经审计评测代码确认此因果”。本次没有完成后者。即使检索诊断有效，也不能据它声称两个生成器的答案质量等效。原稿对 `visual_retriever_only` 的免责声明不能自动覆盖两条标成完整 QA 的路线。

### 4.3 已有实验材料没有转化成论文证据

| ID / 优先级 | 问题与来源 | 证据和处理目标 |
| --- | --- | --- |
| **R10 / P1** | 缺少 oracle-regret，不能直接回答 router 选得好不好。R1；R2 提问逐样本最优选择 | **评审报告**：1,090 条 controller 预测有诊断。MMDocRAG 为 0.3460，对 oracle 0.4326，差 0.0866（8.66 分），oracle 所选路由都可达。FinanceBench 的全路线 oracle 0.2935 对 0.1510 不宜全部归咎 router：79 例选 direct、22 例选 guarded，都不在 allowed set；可达路线 gap 为 0.0263（2.63 分）。应同时报告 oracle 定义和可达范围 |
| **R11 / P1** | 计算了 bootstrap CI 却完全未报告，丢失了支持和反驳主张的信息。R1 | **评审报告**：主表三数据集 controller−text 的区间跨 0；另有四项对 guarded/element/page-image 的正向区间不跨 0；RAGTruth 对 text 为 [−0.0241, −0.0030]，即 [−2.41, −0.30] 分。后续报告配对方式、重采样单位、置信水平和区间，保留负结果 |
| **R12 / P1** | “many ties”的笼统描述遮蔽不同任务上的结果。R1 | **评审报告**：QASPER 194/200、ALCE 185/200 确实多 ties；MMDocRAG 21/120、RAGTruth 81/300 不应同样概括。应按数据集呈现 win/loss/tie，并明确定义 tie |
| **R13 / P1** | 缺少实际交互延迟，尤其多模态长尾。R1、R2 | **评审报告**：MMDocRAG controller 平均 22.37s、p95 101.54s；text 平均 14.33s、p95 38.48s。后续交代端到端计时、冷/热启动、超时处理及用户等待体验；未校准 cost units 不能替代这些时间 |
| **R14 / P1** | 声称衡量的指标没有报告。R1、R2 | **原稿已核对**：§3.1.2 列出 EM、unsupported-claim rate、route-switch rate、errors、timeouts、latency 等，主表缺少多项；评审还要求实际成本。后续选出直接支撑质量、验证、路由和可用性的最小主表，其余给明确附录位置，不能只列指标名字 |
| **R15 / P1** | route-switch/recovery 很少发生，算法叙述与实证重要性不匹配。R1；R2 要求发生条件/频次 | **评审报告**：10/1,090 controller 预测发生切换，约 0.92%。应分清 planned/attempted/completed switch，报告成功与失败，并给真实案例；与 R06 的模式门控一起解释 |
| **R16 / P1** | MMDocRAG controller 与对照路线使用不同 timeout manifest，未披露。R1 | **评审报告**：4 个 controller shards 使用扩展超时的独立 manifest；其他路线用公共 manifest，默认 90s。需列出实际超时、代码版本和 rerun 身份，评估比较公平性。附录对另一项 RAGTruth rerun 的说明不能替代此披露 |
| **R17 / P1** | 已有能直接说明 probe scorer 有作用的正面机制证据没有使用。R1 | **评审报告**：SlideVQA heuristic planner 在 87/120 例提议 text，probe scorer 最终 120/120 选 page-image；visual confidence 0.77–0.89，text 0。可作为路由机制案例/消融线索，但不能替代 R09 所缺的有效生成质量评价 |

对 R11 的统计解释必须克制：区间包含 0 表示在该分析下未明确检测到差异，**不自动证明等效或非劣**。若需要严格“保持质量”的结论，应说明允许的差异范围与相应设计；也可以把现有结论限定为观察到接近的点估计及其不确定性。

R1 批评的不只是“漏一张表”，而是 oracle、CI、延迟/失败、win/loss/tie 四类已有诊断同时缺席，导致论文强调可观察性，却没有充分审视自身。应先整理现有可靠材料，再决定哪些修复需要重跑，不能用扩大实验数量替代解释。

### 4.4 演示、分发和实际用户体验

| ID / 优先级 | 问题与来源 | 证据和处理目标 |
| --- | --- | --- |
| **R18 / P0** | 视频与声称演示/评测版本和后端不一致。AC、R1 | **评审报告**：视频为 v0.0.18、Deepseek、Google embeddings；论文/补充包写 v0.0.40、Qwen3-8B、bge-m3。应固定演示 build、commit、模型和数据，重录或明确解释差异；论文、截图、视频、release 与实验身份必须能互相对上 |
| **R19 / P1** | 视频没有展示中心机制。AC、R1、R3 | **评审报告**：只在一个 7 页 DOCX 上走文本路线，没展示真实视觉问题、混合/graph 场景、切换、失败验证、恢复或拒答。后续在 150 秒内选有代表性的真实任务，并展示 route/evidence/verification 变化；不要求为了覆盖所有内部 route 而制作不真实的演示 |
| **R20 / P0** | 面向非开发者的安装路径不可用。AC、R1 | R1 指出 clone 后开发安装可用，但 README 的 `mara-research-cli` 包名在两个索引都不存在。**本轮独立复核**：PyPI 和 TestPyPI JSON 均为 404。后续应提供真实下载与安装路径，并在干净环境从该路径验证到一次 QA；本轮未安装、未发布包 |
| **R21 / P1** | “local-first”缺少硬件、资源与运行条件说明。R1 | **评审报告**：benchmark 每 shard 使用 2 张 L40S。需区分实验机器配置、最小可用配置与推荐 demo 配置，并说明模型存储、内存/显存、外部 endpoint 依赖。不能据 2×L40S 推断最小硬件要求 |

R19 中值得保留的现有内容也要明确：R1 认可视频展示了可用的 indexing、page preview、citation chips 和 reasoning-status card；问题在于这些还不足以证明核心路由/多模态机制，而不是认定整个视频无效。

公开可用性核验：

- [v0.0.40 release](https://github.com/262412/MARA/releases/tag/v0.0.40) 存在；[GitHub release 元数据](https://api.github.com/repos/262412/MARA/releases/tags/v0.0.40) 列有 [slide-app.zip](https://github.com/262412/MARA/releases/download/v0.0.40/slide-app.zip) 和 [benchmark synthesis ZIP](https://github.com/262412/MARA/releases/download/v0.0.40/mara-full-system-benchmark-synthesis-v0.0.40.zip)。本轮核对了资产元数据，没有把“存在附件”当作“安装成功”。
- [PyPI 包元数据地址](https://pypi.org/pypi/mara-research-cli/json) 与 [TestPyPI 包元数据地址](https://test.pypi.org/pypi/mara-research-cli/json) 在 2026-09-22 的无登录请求均返回 404；这仅针对该确切包名。
- 原稿中的 [YouTube 视频](https://youtu.be/owRaHCzSVNg) 可被公开检索到标题，但本轮没有实际播放，视频的版本、模型、时长和场景仍以评审报告/待复查状态记录。

### 4.5 可读性、计数和归属

| ID / 优先级 | 问题与来源 | 证据和处理目标 |
| --- | --- | --- |
| **R22 / P2** | 41 artifact sets 的单位未在主文解释，3,540 也容易被误读为独立题目。R1 | **原稿已核对**：附录说明 records 是 route-level rows；覆盖 6 个数据集，主表选 3 个。应在首次出现时定义产物集、shard、route record 和 unique question 的关系，并解释 6 个数据集/主表 3 个的关系 |
| **R23 / P1** | 全文需要较大语言和结构整理。AC、R1、R2、R3 | **原稿已核对**：`Our result show`、`MARA perform competitive`、`false abstenti`、`behaviours.MARA` 等，以及摘要对 workbench 使用“model”。应在科学主张确定后统一术语、句法、空格和段落逻辑；不能只做语法润色而保留错误结论 |
| **R24 / P2** | NOTICE 仍用旧产品名。R1 | **评审报告**：上游归属已正确保留，所以不能写成未履行许可义务。后续核对被提交版本的 NOTICE，修正自身产品标识，保留应有上游署名 |

原稿覆盖表的计数为：ALCE-ASQA 4 sets/600 records、FinanceBench 3/600、MMDocRAG 20/600、QASPER 4/600、RAGTruth 6/900、SlideVQA 4/240；合计 **41 / 3,540**。这不是 3,540 个互不重复的题目，也不是 41 条不同算法路线。本轮只核对了稿内加总，没有把它当作对原始产物完整性的再次认证。

## 5. 本轮额外发现的源码与格式问题

这些是本次审核发现，不归到原审稿人的名下。

| ID / 优先级 | 本次证据 | 后续处理目标 |
| --- | --- | --- |
| **S01 / P0** | `paper_venue.tex`、`paper_anonymous.tex` 未定义 `\Xiao`，均在 `paper_body.tex:21` 以 `Undefined control sequence` 失败；`main.tex:19` 才有定义 | 确定唯一投稿入口，清理/一致处理修订宏。两个备用入口当前不能宣称可直接构建 |
| **S02 / P0** | `paper_body.tex:437` 的 `\ifmaraanonymous` 有 `\else`，文件结束前没有对应 `\fi`。`main.tex` 虽输出 PDF，但日志有 `\end occurred when \iffalse ... was incomplete` | 修复条件结构后重新构建；不能把退出码 0 视作没有文档结构问题 |
| **S03 / P0** | `main.tex` 作者为 Chenghao Zhang、Ke Xu、Xiao Xiao、Meng Fang；`paper_venue.tex` 少 Ke Xu。两者标题也不同，匿名入口另有匿名作者 | 由作者确认最终名单、顺序、单位和题目，再统一 PDF 与 OpenReview 元数据；本轮不自行增删作者 |
| **S04 / P1** | `paper_body.tex:478–480` 的整体 limitations/next steps 被注释；当前仍在其他段落零散承认 smoke retriever、VLM fallback、graph/element 原型和非官方 evaluator | 把影响解释的限制明确写进可见正文/相应讨论，尤其控制器未校准、VLM 是否实际启用、评测边界；源码注释不等于读者看得见的披露 |
| **S05 / P1** | Algorithm 1 显式列出检索及 answer-support check，却没有单独列出生成 answer 的步骤；失败后的重检索、重新生成和再验证也未展开 | 与实际默认/严格模式对齐，说明何时生成、何时验证、失败后执行哪些步骤，避免流程读起来像验证尚未生成的答案 |
| **S06 / P1** | 原稿有 privacy-conscious/local-first 表述，同时允许显式配置模型 endpoints；评审视频还报告了外部 provider | 说明哪些数据留在本地、哪些会发给配置的服务，以及日志/演示材料的范围。对于当前显示的非敏感示例，不无依据地声称发生隐私违规 |
| **S07 / P2** | 第 3 页算法用 `\scriptsize`，图中也有较小文本；原始 UI 图可读，但缩入论文后细节有限 | 按 A4 实际尺寸检查核心标签与状态，优先压缩冗余的 route 映射/实现文字，避免靠继续缩小字体腾页数 |
| **S08 / 待核对** | 实名入口无审稿行号；所有作者邮箱被省略，单位地址也较简略 | 对照 Demo 表单及 ACLPUB 格式要求处理行号、完整单位信息和作者元数据；不要把邮箱建议性要求误写成单独的拒稿结论 |

当前两个官方样式文件不需要因为“转投”就擅自替换：`acl.sty` 和 `acl_natbib.bst` 的内容与核验时官方 master 文件逐字节相同。若后续会方发布更新，再按实际要求处理。

没有发现需要为此修改产品公开命令、数据库或运行环境的理由。源码已有错误按用户要求仅记录，未修复。

## 6. 后续修改工作包及验收条件

以下是准备好的待办顺序，不代表已经执行，也不是要求先完成庞大新实验才允许推进。

| 顺序 | 工作包 | 可验收结果 | 覆盖问题 |
| --- | --- | --- | --- |
| 1 | 固定投稿身份和材料版本 | 最终作者/题目确认；单一 LaTeX 入口无错误；demo build、代码 commit、模型、release、视频和论文能互相对应；三项必交材料明确 | R18、R20、S01–S03、S08 |
| 2 | 消除错误主张 | 引言、摘要、结果和结论与表格一致；competitive 的对象明确；没有把 proxy、证据检索或统计不显著写成质量提升 | R01–R04、R07、R11、R23 |
| 3 | 审计两类评测/路由关键问题 | 确认 SlideVQA 的 evaluator 是否使用生成答案；重建 RAGTruth 214/83/其余例的路由和得分；明确实际 VLM 使用与 retry 门控 | R05–R09、R15、S05 |
| 4 | 把已有有效诊断放进论文 | 主文出现与贡献直接相关的路由分布、可达 oracle gap、配对 CI、质量/延迟和失败数据；负结果有解释；主表与附录有精确引用 | R03、R10–R17、R22 |
| 5 | 证明相对上游的实际增量 | 在可比条件下给出 Kotaemon 基线/消融及功能边界；用具体用户任务说明可观察性解决了什么问题 | R02、R04 |
| 6 | 准备一致且有区分力的演示 | 实际录制 ≤150 秒；展示真实多模态证据与至少有代表性的验证/恢复或拒答场景；可追踪版本、后端和限制 | R18–R21、S06 |
| 7 | 投稿前检查 | 修订后的正文 ≤6 页；两类链接都在 PDF/表单；下载路径到 QA 的最小流程成功；字体/行号/可读性/声明检查完毕 | EACL 要求、R20、R23–R24、S04、S07–S08 |

**实验版本处理原则：**保留原始 41 组产物、3,540 条 route-level 记录作为历史基线；不要把修复后的个别结果混回原表。新增运行要有自己的 manifest、代码与模型版本、计时/超时条件和 evaluator 身份。是否需要完整重跑，应由修复实际影响的样本和比较决定，本轮未做这一决策。

**篇幅安排建议：**将正文中过细的内部 route ID 映射、平台包装器和命令罗列适当移到信息性附录，为核心机制、有效性、代价与失败分析留出空间。关键证据必须在主文可见，不能只写“附录 ZIP 里有”；审稿人不必阅读所有补充材料。

## 7. 评审覆盖对照

| 来源 | 其提出的问题在本文中的位置 |
| --- | --- |
| AC | 质量/核心主张 R01–R03；RAGTruth/SlideVQA R08–R09；Kotaemon R04；技术细节 R05；视频 R18–R19；安装 R20；重写 R23 |
| R1 | 方法和默认 retry R05–R07；主张/内外对照/路由休眠 R01–R04；四类诊断 R10–R15；RAGTruth R08；SlideVQA R09；实际生成器 R07；视频 R18–R19；安装 R20；未披露 timeout R16；正面 probe 案例 R17；硬件 R21；计数 R22；EM 漏报 R14；NOTICE R24 |
| R2 | 缺少明显收益 R02；上游增量 R04；规则/公式/阈值/切换 R05–R06；路由频次与逐样本最优 R03、R10、R15；VLM/fallback 身份 R07；欠缺系统指标 R13–R14；表达 R23 |
| R3 | 上游增量 R04；controller 与视觉收益 R02；视频缺少多模态/失败/恢复/拒答 R19；较大语言修改 R23 |

这份清单覆盖作者提供的 AC 和三位 reviewer 的实质问题及 R1 的 minor issues；没有将未取得的独立最终 Decision 或其他未提供评论虚构为已读材料。

## 8. 本轮验证记录与未验证事项

### 已执行

- 解压并保存原 ZIP；10 个文件在解压时与检查结束时 SHA-256 均匹配。
- 在独立分支/工作区组织文件；未修改已有运行代码和原论文文件。
- 使用已有 TeX Live 2025 / pdfLaTeX / latexmk，通过 LaTeX 插件构建三入口。`main.tex` 成功生成 9 页，另两个因 `\Xiao` 未定义失败；主入口的未闭合条件告警已记录。
- 从生成 PDF 核对正文结束于第 6 页、参考文献在第 7 页、附录在第 8–9 页；检查第 3、6 页渲染及原 UI 图。没有声称完成所有页面的逐像素审查。
- PDF 为 A4（595.276 × 841.89 pt），6 种字体全部嵌入；摘要按空白分词计 148 词；主构建没有报告 overfull box 或 undefined citation/reference。
- 核对官方 CFP、格式说明、两个官方 style 文件的 SHA-256、GitHub release 资产列表，以及两个包索引对确切包名的 404 响应。
- 将作者提供的 4 份评审文本逐项映射到 R01–R24，并另列 S01–S08 的本次发现。

### 未执行或仍需作者/后续工作确认

- 没有通过 browser 直接读到 OpenReview 评审；没有独立最终 Decision 的全文。
- 没有重算补充包的 CI、oracle、路由统计和逐样本得分，也没有审计对应提交版本的 evaluator/路由代码。
- 工作区已有 `docs/demo_paper/mara-full-system-benchmark-synthesis-v0.0.40.zip`，release 也有同名附件；原用户提供的源码 ZIP 不含该补充包。本轮没有把它们认定为同一字节版本或擅自混并。
- 没有播放或重录视频，未确认原视频时长和匿名/公开访问体验。
- 没有在干净环境安装软件、下载模型或验证一次实际 QA；安装包存在不能替代这些检查。
- 没有确认最终作者名单、其他在审稿件、指定 reciprocal reviewer、会场演示安排，也没有填写或提交 EACL 表单。
- 没有修论文、改产品、修 evaluator、重跑实验或发布新版本。

本清单作为后续修改与验收的基线；其中的修改项当前均为待处理。
