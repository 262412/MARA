# MARA EACL 2027 Overleaf 项目

上传文件：MARA-EACL2027-Overleaf.zip。

2026-09-23 更新：已同步公开 Release 的新版 Windows 安装包，移除将历史 `uv sync --extra mara` 当作评审快速安装路线的说明，并明确新安装包与 v0.0.40 源码/benchmark 的区别。

在 Overleaf 中选择 New Project → Upload Project，直接选择 ZIP；无需先解压。上传后确认 Main document 为 main.tex，Compiler 为 pdfLaTeX。项目已用本地 TeX Live 2025 编译验证；若 Overleaf 提供 TeX Live 2025，可选择同一版本。

项目根目录只保留 main.tex 一个编译入口，以避免误选匿名版。论文内容、作者、图和参考文献与当前 EACL 修订稿一致。main.tex 使用带作者的 ACL 审稿样式，保留行号和页码。

文件分工：

- main.tex：标题、作者、宏包、主文件结构。
- paper_body.tex：摘要和正文。
- appendix.tex：附录文字及实现细节。
- diagnostic_tables.tex：完整诊断表。
- references.bib：参考文献。
- figures/mara-ui-qa.png：界面截图。
- acl.sty、acl_natbib.bst：官方样式和参考文献格式。
- README-overleaf.txt：包内上传与编译说明。

参考文献由 BibTeX 自动处理。首次编译等待其完成；无需上传本地 PDF、编译日志、benchmark ZIP 或 Git 文件。本包不包含旧 EMNLP 稿件和匿名备用入口。

预期输出为 11 页，主内容在第 5 页结束。Overleaf 云端编译尚未实际执行；本地解压编译检查见 audit/overleaf-package-check.json。
