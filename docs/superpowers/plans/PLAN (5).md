# MARA Benchmark 跑分与测试计划表

## Summary

MARA 的 benchmark 不做“大一统 leaderboard”。本计划把测试分成 **系统可用性测试、路线诊断测试、端到端 DocQA 主实验、路由能力分析、幻觉/护栏分析、效率分析** 六类。

统一运行路径：

| 项 | 路径 |
|---|---|
| 数据集 | `/mnt/scratch/users/tbczhang/datasets/MARA` |
| 输出 | `/mnt/scratch/users/tbczhang/outputs/MARA` |
| HF cache | `/mnt/fastscratch/users/tbczhang/cache/huggingface/hub` |
| 主 LLM | `Qwen/Qwen3-8B` |
| VLM | `Qwen/Qwen3-VL-8B-Instruct` |
| Text embedding | `BAAI/bge-m3`, `Qwen/Qwen3-Embedding-8B` |
| Reranker | `BAAI/bge-reranker-v2-m3`, `Qwen/Qwen3-Reranker-4B` |
| Visual retriever | `vidore/colqwen2-v1.0-hf`, `vidore/colpali-v1.3-hf` |

## Benchmark 总表

| 编号 | 测试类型 | 目的 | 数据集 | 路线 | 样本量 | 主要指标 | 是否主实验 |
|---:|---|---|---|---|---:|---|---|
| T0 | Route smoke test | 确认所有 MARA 路线能跑、不崩、不误标 backend | 自建 5-10 条小样本 + FinanceBench 小样本 | `direct_answer`, `text_rag`, `page_image_rag_smoke`, `page_image_rag_vlm`, `element_rag`, `graph_rag_local`, `hybrid_rag`, `controller_auto`, `crag_guarded` | 5-10 | crash rate, skipped routes, evidence presence, trace presence | 否 |
| T1 | Text QA baseline | 验证 text RAG 与 controller 在纯文本/财报 QA 上的表现 | FinanceBench | `direct_answer`, `text_rag`, `hybrid_rag`, `controller_auto`, `crag_guarded` | smoke 10；main 50-100 | EM/F1, citation recall, evidence hit, latency | 是 |
| T2 | Scientific DocQA | 测科研论文 QA、证据引用、summary/compare 问题 | QASPER | `text_rag`, `graph_rag_local`, `hybrid_rag`, `controller_auto`, `crag_guarded` | 50-100 | F1, evidence hit, source recall, graph route usefulness | 是 |
| T3 | Multimodal DocQA | 测多页、多模态文档 QA | MMDocRAG / MMDocIR | `text_rag`, `page_image_rag_vlm`, `element_rag`, `hybrid_rag`, `controller_auto` | 50-100 | page hit, image/table evidence hit, multimodal support, answer F1 | 是 |
| T4 | Slide QA | 测 slide/page-image/element 路线 | SlideVQA | `text_rag`, `page_image_rag_vlm`, `element_rag`, `hybrid_rag`, `controller_auto` | 50-100 | page hit, visual support, element hit, answer F1 | 是 |
| T5 | Visual retrieval diagnostic | 单独测 ColPali/ColQwen 是否找对页面 | ViDoRe subset | `page_image_rag_vlm` 的 retriever-only 版本；对比 ColPali vs ColQwen | 100-300 queries | recall@1, recall@5, MRR, retrieval latency | 辅助主实验 |
| T6 | Hallucination / Guardrail | 测 CRAG/verifier 是否减少 unsupported answer | RAGTruth | `text_rag`, `controller_auto`, `crag_guarded` | 50-100 | unsupported claim rate, contradiction count, abstention correctness, false abstention | 是 |
| T7 | Citation quality | 测引用质量，不追求完整 ALCE 复现 | ALCE | `text_rag`, `hybrid_rag`, `controller_auto`, `crag_guarded` | 50-100 | fluency, correctness, citation precision/recall, attributable claim rate | 辅助主实验 |
| T8 | Element/layout diagnostic | 测 element parser / layout evidence 覆盖 | DocLayNet + SlideVQA subset | `element_rag`, `hybrid_rag` | 50-100 pages/items | element type hit, table/figure/formula hit, layout coverage | 否，诊断测试 |
| T9 | Efficiency test | 测系统代价 | FinanceBench + SlideVQA + MMDocRAG 小样本 | `text_rag`, `page_image_rag_vlm`, `hybrid_rag`, `controller_auto`, `crag_guarded` | 每组 20-50 | index time, generation latency, route overhead, GPU memory if available | 辅助主实验 |

## 主实验路线分组

| Route group | 路线 | 用途 | 报告方式 |
|---|---|---|---|
| Lower bound | `direct_answer` | 无检索下界 | 只在 FinanceBench / smoke 中报告，不进入所有平均值 |
| Text baseline | `text_rag` | 固定 text RAG baseline | 所有主实验必须有 |
| Multimodal specialist | `page_image_rag_vlm`, `element_rag` | 视觉/布局/元素问题 | 只在 SlideVQA、MMDocRAG、ViDoRe、DocLayNet 相关实验中报告 |
| Graph specialist | `graph_rag_local` | summary / compare / connect-the-dots | 只在 QASPER / 自建 global questions 中报告 |
| Hybrid route | `hybrid_rag` | 多证据融合 | 主实验核心对比 |
| Proposed controller | `controller_auto` | MARA 核心贡献 | 主实验核心对比 |
| Guarded controller | `crag_guarded` | Self-RAG/CRAG-style 护栏 | 主实验核心对比 |

主表默认只比较：

```text
text_rag
hybrid_rag
controller_auto
crag_guarded
```

multimodal 子表再加入：

```text
page_image_rag_vlm
element_rag
```

graph 子表再加入：

```text
graph_rag_local
```

## 运行阶段计划

| 阶段 | 目标 | 数据集 | 样本量 | 通过标准 |
|---:|---|---|---:|---|
| P0 | 环境确认 | 无 | 无 | `MARA docqa doctor` 通过；vLLM `/v1/models` 可访问；输出目录在 scratch |
| P1 | 最小闭环 | FinanceBench | 10 | `text_rag`, `controller_auto`, `crag_guarded` 都能生成 answer/evidence/trace |
| P2 | 路线 smoke | FinanceBench + 自建 multimodal 小样本 | 5-10 | 所有 route 不崩；未配置 route 正确出现在 skipped route table |
| P3 | Text 主实验 | FinanceBench, QASPER | 50-100 each | 生成 route-level CSV/Markdown；text baseline 可解释 |
| P4 | Multimodal 主实验 | SlideVQA, MMDocRAG | 50-100 each | page-image / element / hybrid 至少一个子集优于 text RAG 或提供明确错误分析 |
| P5 | Visual retriever 诊断 | ViDoRe subset | 100-300 | 报告 ColPali vs ColQwen recall@k/MRR，不混入 QA 总分 |
| P6 | Guardrail 实验 | RAGTruth | 50-100 | `crag_guarded` unsupported claim rate 低于 `text_rag` 或解释 abstention trade-off |
| P7 | Citation 辅助实验 | ALCE | 50-100 | 报告 citation precision/recall，不声称完整复现 ALCE |
| P8 | 效率实验 | FinanceBench + SlideVQA + MMDocRAG | 20-50 each | 报告 latency/index time/route overhead |
| P9 | Thesis tables | 全部主实验输出 | 汇总 | 形成主表、子表、错误案例表、route confusion matrix |

## 输出与报告表

| 输出文件/表 | 内容 | 用途 |
|---|---|---|
| `summary.json` | 每次 run 的整体指标 | 自动汇总 |
| `predictions.jsonl` / equivalent | 每条样本的 answer、evidence、trace、metrics | 错误分析 |
| Route-level results table | dataset × route × metric mean | 论文主表 |
| Routing confusion matrix | expected route vs selected route | 证明 controller 是否有效 |
| Skipped backend table | 哪些 route 因未配置 backend 被跳过 | 防止污染均值 |
| Error case table | retrieval miss、wrong route、unsupported claim、bad citation、VLM failure | 论文 qualitative analysis |
| Efficiency table | latency、index time、route overhead | 系统可行性分析 |

## 指标计划

| 能力 | 指标 | 适用数据集 |
|---|---|---|
| 答案正确性 | EM, F1, ANLS | FinanceBench, QASPER, SlideVQA, MMDocRAG |
| 证据质量 | citation recall, citation precision, evidence hit | FinanceBench, QASPER, ALCE |
| 页面检索 | page hit, recall@1, recall@5, MRR | ViDoRe, SlideVQA, MMDocRAG |
| 多模态支持 | image quote hit, table hit, figure hit, multimodal support | SlideVQA, MMDocRAG |
| Element 能力 | element hit, layout type hit, table/figure/formula hit | DocLayNet, SlideVQA |
| Graph 能力 | source coverage, global summary support, qualitative connect-the-dots score | QASPER, 自建 global questions |
| 路由能力 | route accuracy, route confusion, route switch rate, fallback rate | 所有 route-labeled 子集 |
| 护栏能力 | unsupported claim rate, contradiction count, abstention rate, false abstention | RAGTruth, CRAG runs |
| 效率 | index time, retrieval latency, generation latency, total latency | 所有主实验 |

## 明确不做的测试

| 不做 | 原因 |
|---|---|
| 不做所有数据集的统一平均分 | 数据集任务类型不同，平均值会误导 |
| 不让 GraphRAG 回答普通 page-specific QA | graph route 是 global/summary specialist |
| 不把 `page_image_rag_smoke` 当真实 VLM/ColPali 结果 | smoke backend 只用于功能验收 |
| 不把未配置 external evaluator 的 proxy metric 当 paper-grade 指标 | 必须在报告中标明 proxy / not_configured |
| 不第一轮跑 DocLayNet 全量 | zip 28G，且 element/layout 不是主 QA benchmark |
| 不追求完整复现 ALCE/MMDocRAG/RAGTruth leaderboard | 硕士论文目标是 route-level ablation 和系统分析 |

## Assumptions

- 默认主模型使用 `Qwen/Qwen3-8B`，因为当前本地已安装且适合先跑完整闭环。
- 默认 VLM 使用 `Qwen/Qwen3-VL-8B-Instruct`。
- 默认 text embedding 先用 `BAAI/bge-m3`，后续用 `Qwen/Qwen3-Embedding-8B` 做 embedding ablation。
- 默认 reranker 先用 `BAAI/bge-reranker-v2-m3`，后续用 `Qwen/Qwen3-Reranker-4B` 做 reranker ablation。
- `FinanceBench` 和符合 JSON+documents 结构的 `SlideVQA` 可直接走现有 normalizer；`MMDocRAG`, `ViDoRe`, `QASPER`, `ALCE`, `RAGTruth`, `DocLayNet` 需要先转成 MARA manifest 或 evaluator input。
- 所有输出写入 `/mnt/scratch/users/tbczhang/outputs/MARA`；不在 fastscratch 解压大数据集或写大量小文件。
- 论文主结论围绕：**controller_auto 与 crag_guarded 是否比 fixed text_rag 更会选路线、更能利用多模态证据、更少 unsupported claims**。
