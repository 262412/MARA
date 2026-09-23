# OpenReview 投稿字段草稿

这是供作者复制填写的材料，不表示表单已填写或已提交。具体字段名和必填项以实际 EACL Demo 表单为准。

投稿入口：https://openreview.net/group?id=eacl.org/EACL/2027/Demo

截止时间：北京时间 2026-09-23 19:59，即官方 2026-09-22 23:59 UTC−12。要求来源：https://2027.eacl.org/calls/demos/

## Title

LMDoc: A Local-First Workbench for Observable Multimodal Document Question Answering

## Abstract

LMDoc is a local-first document-QA workbench that records which evidence was retrieved, which route was selected, and why an answer was returned or withheld. Built on Kotaemon, it helps researchers and technical users inspect answer stages, change sources or routes, and test suspected failure causes through Web, command-line, and diagnostic workflows. Two forms of evidence illustrate this use. A historical benchmark bundle spanning six datasets exposes routing failures and trade-offs, with no consistent F1 advantage over fixed text retrieval. Two case studies connect recorded decisions to interventions: replaying the same recorded claims tests a targeted verifier repair, and a public-chart comparison examines the effect of including image evidence. We release the Apache-2.0 implementation, captured case inputs and outputs, reproduction scripts, and a demonstration of the document-QA interface.

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

- Paper: LMDoc-EACL2027.pdf
- Supplementary artifacts: LMDoc-EACL2027-supplement.zip（若表单有相应附件入口）
- Source backup: LMDoc-EACL2027-Overleaf.zip（供 Overleaf/归档；不是论文 PDF 的替代品）

## Already confirmed

四位作者信息按原 main.tex 保留；不存在显著重叠的其他在审或已发表稿件；Chenghao Zhang 作为互惠审稿人；沿用原视频；本轮保留历史 benchmark，另增小规模诊断执行与对照，不作为新 benchmark。

## Before pressing Submit

核对作者 profile、PDF 和正确附件，确认链接在审稿人视角可访问，按表单填写必填声明并确认实际提交状态。本地文件生成和 Git commit 不等于 OpenReview 投稿成功。接受后至少一名作者须注册并现场演示及提供海报；该安排尚未执行。

## TL;DR

LMDoc records evidence, routes, and answer stages so users can inspect document-QA failures and test interventions.

本轮需同步替换 PDF、补充包和摘要；视频及软件下载链接保持不变。尚未在 OpenReview 替作者提交。

## 演示名称说明

论文统一使用 LMDoc。原视频、界面截图、已发布软件和历史记录继续显示 MARA；正文演示部分及附录 C.2 已解释二者的对应关系。实际命令和链接保持原值。重新上传时同步修改标题、摘要、TL;DR、PDF 和补充 ZIP。

本轮修订收窄有用性结论，加入原始回答对照、具体验证器修复和真实图表干预。修复补丁随补充包提供，尚未替换已发布安装包；历史 SlideVQA 原始输出暂无副本。
