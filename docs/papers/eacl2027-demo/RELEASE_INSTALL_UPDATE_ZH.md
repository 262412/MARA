# v0.0.40 Release 安装包替换与源码路径复测

日期：2026-09-23（Asia/Shanghai）。本记录接续此前 Windows 安装审计和新安装 ZIP 的本机构建测试。

## 发布结果

已按作者要求，在 [v0.0.40 Release](https://github.com/262412/MARA/releases/tag/v0.0.40) 替换旧 `slide-app.zip`，保持原下载地址可用，并增加 `slide-app.zip.sha256`。Release 顶部现在包含安装步骤、网络和模型服务前提，以及新安装包与历史源码的版本区别。

| 项目 | 当前值 |
| --- | --- |
| Release ID | `351050065` |
| 新安装附件 ID | `581920260` |
| 文件 | `slide-app.zip`，33,918,912 bytes |
| SHA-256 | `886b949135ce74f123e0ae7b8a81c533594f0e98739b8057c277485ec3fb1432` |
| 新包源提交 | `e6afa5dcda18ef6d5d6aae2efb0f1a6b806187b3` |
| main 基线 | `dfcca9987fa4f4d3c5e4da303217c32692032b65` |
| 新包应用版本 | `0.0.41` |
| 保留的 v0.0.40 Git 标签 | `37487f35610076c1016e1b59d3bf982388d1a275` |

公开 ZIP 下载地址：
<https://github.com/262412/MARA/releases/download/v0.0.40/slide-app.zip>

旧安装附件 ID `470442677` 已删除；其原始文件在删除前下载并核对 SHA-256，保留于本机备份。新包曾以带提交名的文件名上传，GitHub 返回的 digest 与本地一致后，才替换旧附件名称。原 benchmark 附件 ID `474358900`、大小与 SHA-256 均未改变。没有移动标签或合并/推送代码分支。

匿名公开下载最终文件返回 HTTP 200，完整下载 33,918,912 bytes，SHA-256 与已完成本机安装测试的 ZIP 完全一致。校验文件可匿名读取；公开 Release HTML 已显示新的安装说明。首次临时下载遇到超时，后用 curl 完成最终地址下载；未降低 TLS 校验要求。远程标签的一次 Git 查询遇到连接重置，随后通过 GitHub REST API 确认标签 SHA 未变。

## 原论文源码命令的复测结果

在全新 standalone clone 中执行原命令：

```text
git clone --branch v0.0.40 https://github.com/262412/MARA.git
cd MARA
uv sync --extra mara
```

clone 成功，HEAD 为历史标签 `37487f35`。安装使用独立目录的 Python 3.10.19 虚拟环境，不同步开发工作区。`uv sync --extra mara` 退出码为 1，失败依赖链为：

```text
mara-app -> kotaemon[all] -> llama-cpp-python==0.2.7
```

编译报错包括 `nmake` 不存在、`CMAKE_C_COMPILER` 和 `CMAKE_CXX_COMPILER` 未设置。源码和 lock 文件没有因测试发生变化。该结果针对本次 Windows 环境；不能推断所有配备编译器的 Linux 或 Windows 开发环境都会失败，也没有证明安装编译器后整个旧版本就一定可以运行。

结论：论文需要修改安装建议。替换 release 附件不会改变 `git clone --branch v0.0.40` 的内容，因此不能保留“这几条命令即可供评审安装”的暗示，也不能把新 ZIP 说成 v0.0.40 原实验构建。当前评审入口应为解压 ZIP、运行 `Install.cmd` 与 `Start.cmd`；保留 tag clone 作为历史源码查看路径。新的可克隆源码安装路线尚未在远端发布或验证，不能列为已完成。

## 论文与交付材料

已更新主文 access 段、附录安装说明、`ARTIFACT_GUIDE.md` 和投稿字段中的下载入口。实验数值、表格、作者、参考文献、图和原视频保持原样。重新生成论文 PDF、Overleaf ZIP、完整源码 ZIP 与补充材料 ZIP；补充包内的原始 benchmark ZIP 逐字节保留。

本地 TeX Live 2025 编译以及 Overleaf ZIP 全新解压后的编译均通过；完整论文仍为 11 页，主内容在第 5 页结束。变更相关页面已渲染检查，未发现超出边界、内容重叠或引用缺失。Overleaf 云端编译和 OpenReview 提交没有执行。

新包本机安装与 UI 启动已验证，但真实模型索引/问答、视觉/图后端以及其他操作系统仍未验证。评审需配置生成模型和 embedding 服务，首次安装需要联网；不能把该包描述为无需配置即可离线问答。

机器可读记录见 `audit/release-install-update.json`、`audit/overleaf-package-check.json`。完整发布、下载与源码复测日志保存在 `D:\MARA-reviewer-build\20260923-release-v0.0.40`；旧论文交付文件备份位于其 `paper-artifacts-before` 子目录。
