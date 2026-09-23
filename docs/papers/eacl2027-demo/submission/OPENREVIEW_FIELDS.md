# OpenReview 投稿字段草稿

这是供作者复制填写的材料，不表示表单已填写或已提交。具体字段名和必填项以实际 EACL Demo 表单为准。

投稿入口：https://openreview.net/group?id=eacl.org/EACL/2027/Demo

截止时间：北京时间 2026-09-23 19:59，即官方 2026-09-22 23:59 UTC−12。要求来源：https://2027.eacl.org/calls/demos/

## Title

DocQA-Inspect: A Local-First Workbench for Observable Multimodal Document Question Answering

## Abstract


Document question answering involves choices about evidence, retrieval, generation, and verification that are difficult to inspect together. We present DocQA-Inspect, a local-first workbench extending Kotaemon with observable route control and shared diagnostic records across Web, command-line, and benchmark workflows. We analyze a released bundle covering six datasets, 1,090 dataset–question pairs, and 3,540 route-level records. Automatic routing does not consistently improve answer F1 over fixed text retrieval; the records expose inactive routing, a weak graph route, multimodal latency, and a non-discriminating visual comparison. A separate, executed diagnostic case follows an unresolved question through successful retrieval, a verification-triggered refusal, source correction, and a supported answer. We provide the case's raw provider outputs, displayed and scoring answers, evidence, effective settings, and offline checks. DocQA-Inspect's contribution is an inspectable workflow for locating such failures, with explicit limits on what the retained evidence can reproduce. We release the Apache-2.0 implementation and diagnostic materials, alongside a user-workflow demonstration.

## Authors（按此顺序）

1. Chenghao Zhang
2. Ke Xu
3. Xiao Xiao
4. Meng Fang

单位：School of Computer Science and Informatics, University of Liverpool

PDF 按要求不显示邮箱；OpenReview 账户联系信息不由本次论文修订更改。

互惠审稿人：Chenghao Zhang（作者已确认）。各作者 OpenReview profile 应由提交人选取匹配记录，不虚构 profile ID 或其他作者邮箱。

## Links

- Demo video: https://youtu.be/owRaHCzSVNg
- Downloadable software / installation guide: https://github.com/262412/MARA/releases/tag/v0.0.40
- Direct Windows x64 installer: https://github.com/262412/MARA/releases/download/v0.0.40/slide-app.zip
- Repository: https://github.com/262412/MARA

视频时长：作者确认正好 2 分 30 秒，未做媒体文件独立测量。视频与下载链接已同时出现在 PDF；提交时也须填入表单。

安装包于 2026-09-23 更新，基于 main 加安装修复（`e6afa5dc`，包版本 0.0.41）；v0.0.40 标签和 benchmark 附件保留历史身份。Windows 安装、网页启动，以及新增案例中的真实模型索引/问答已测；独立重跑仍出现严格验证拒答，结果已保留。跨平台安装未验证。提交时使用 Release 页面作为带说明的下载入口，不把历史 `uv sync --extra mara` 命令写成已验证的通用安装路线。

## Suggested keywords

Document question answering; retrieval-augmented generation; system observability; multimodal retrieval; reproducible diagnostics.

## Attachments

- Paper: DocQA-Inspect-EACL2027.pdf
- Supplementary artifacts: DocQA-Inspect-EACL2027-supplement.zip（若表单有相应附件入口）
- Source backup: DocQA-Inspect-EACL2027-Overleaf.zip（供 Overleaf/归档；不是论文 PDF 的替代品）

## Already confirmed

四位作者信息按原 main.tex 保留；不存在显著重叠的其他在审或已发表稿件；Chenghao Zhang 作为互惠审稿人；沿用原视频；本轮没有新的 benchmark。

## Before pressing Submit

核对作者 profile、PDF 和正确附件，确认链接在审稿人视角可访问，按表单填写必填声明并确认实际提交状态。本地文件生成和 Git commit 不等于 OpenReview 投稿成功。接受后至少一名作者须注册并现场演示及提供海报；该安排尚未执行。

## TL;DR

DocQA-Inspect exposes document-QA decisions and answer stages to support inspectable, reproducible failure diagnosis.

本轮需同步替换 PDF、补充包和摘要；视频及软件下载链接保持不变。尚未在 OpenReview 替作者提交。

## 演示名称说明

论文统一使用 DocQA-Inspect。原视频、界面截图、已发布软件和历史记录继续显示 MARA；正文演示部分及附录 C.2 已解释二者的对应关系。实际命令和链接保持原值。重新上传时同步修改标题、摘要、TL;DR、PDF 和补充 ZIP。
