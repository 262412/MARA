# OpenReview 投稿字段草稿

这是供作者复制填写的材料，不表示表单已填写或已提交。具体字段名和必填项以实际 EACL Demo 表单为准。

投稿入口：https://openreview.net/group?id=eacl.org/EACL/2027/Demo

截止时间：北京时间 2026-09-23 19:59，即官方 2026-09-22 23:59 UTC−12。要求来源：https://2027.eacl.org/calls/demos/

## Title

MARA: A Local-First Workbench for Multimodal Document Question Answering

## Abstract

Document question answering involves choices about evidence, retrieval, generation, and verification that are often difficult to inspect together. We present MARA, a local-first workbench extending Kotaemon with observable route control and a shared diagnostic interface across Web, command-line, and benchmark workflows. A rule-based controller records its proposed, scored, and final evidence routes, heuristic quality and cost estimates, retrieval status, and verification outcomes. We analyze a released benchmark bundle covering six datasets, 1,090 dataset–question pairs, and 3,540 route-level records. Automatic routing does not consistently improve answer F1 over fixed text retrieval. Instead, the records expose largely inactive routing on text-heavy datasets, a graph-route failure on RAGTruth, substantial multimodal latency, and a non-discriminating SlideVQA comparison. These findings illustrate the workbench's diagnostic use while delimiting its current capabilities. We release the Apache-2.0 implementation and benchmark artifacts, and demonstrate source selection, page inspection, citation review, and visible reasoning status in a configurable user deployment.

## Authors（按此顺序）

1. Chenghao Zhang
2. Ke Xu
3. Xiao Xiao
4. Meng Fang

单位：School of Computer Science and Informatics, University of Liverpool

联系邮箱：tbczhang@liverpool.ac.uk

互惠审稿人：Chenghao Zhang（作者已确认）。各作者 OpenReview profile 应由提交人选取匹配记录，不虚构 profile ID 或其他作者邮箱。

## Links

- Demo video: https://youtu.be/owRaHCzSVNg
- Downloadable software / source release: https://github.com/262412/MARA/releases/tag/v0.0.40
- Repository: https://github.com/262412/MARA

视频时长：作者确认正好 2 分 30 秒，未做媒体文件独立测量。视频与下载链接已同时出现在 PDF；提交时也须填入表单。

## Suggested keywords

Document question answering; retrieval-augmented generation; system observability; multimodal retrieval; reproducible diagnostics.

## Attachments

- Paper: mara-eacl2027-demo.pdf
- Supplementary artifacts: mara-eacl2027-supplement.zip（若表单有相应附件入口）
- Source backup: mara-eacl2027-source.zip（供 Overleaf/归档；不是论文 PDF 的替代品）

## Already confirmed

四位作者信息按原 main.tex 保留；不存在显著重叠的其他在审或已发表稿件；Chenghao Zhang 作为互惠审稿人；沿用原视频；本轮没有新的 benchmark。

## Before pressing Submit

核对作者 profile、PDF 和正确附件，确认链接在审稿人视角可访问，按表单填写必填声明并确认实际提交状态。本地文件生成和 Git commit 不等于 OpenReview 投稿成功。接受后至少一名作者须注册并现场演示及提供海报；该安排尚未执行。
