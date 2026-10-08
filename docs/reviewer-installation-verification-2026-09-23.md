# 评审安装 ZIP 验证记录（2026-09-23）

本次已完成 Windows x64 安装 ZIP 的构建与本机安装、启动验证。安装包固定应用文件及依赖版本，脚本自动准备独立 Python 环境。首次安装需要联网；模型服务由使用者配置。本记录不代表真实模型问答、其他操作系统或论文 benchmark 已通过验证。

## 交付物与版本

| 项目 | 值 |
| --- | --- |
| 文件 | `MARA-reviewer-windows-x64-e6afa5dc.zip` |
| 大小 | 33,918,912 bytes，约 33.9 MB |
| SHA-256 | `886b949135ce74f123e0ae7b8a81c533594f0e98739b8057c277485ec3fb1432` |
| main 基线 | `dfcca9987fa4f4d3c5e4da303217c32692032b65` |
| 应用构建提交 | `e6afa5dcda18ef6d5d6aae2efb0f1a6b806187b3` |
| 工作分支 | `codex/reviewer-installer` |
| 四个应用 wheel 的版本 | `0.0.41` |
| Python / uv | `3.10.19` / `0.11.19` |

工作目录是 `C:\Users\22826\.codex\worktrees\mara-reviewer-installer\MARA`。
该分支从已更新的 `origin/main` 创建。原主工作区及其 refactor 分支未修改；论文、Overleaf 项目、v0.0.40 标签和已有 release 均未修改。本次未 push、上传或发布 release。

安装包由上述应用提交构建；本验证文档可以位于其后的文档提交中。包内 `manifest.json` 是应用来源的依据。当前 main 衍生包与原论文 v0.0.40 实验构建不同，不能把本包描述为产生原 benchmark 数字的同一构建。

## 评审操作

1. 完整解压到可写目录，建议至少保留 8 GB 空间，安装后保持目录位置不变。
2. 双击 `Install.cmd`。脚本安装 Python、创建独立环境、安装锁定依赖和包内应用 wheel，运行一致性检查。
3. 成功后双击 `Start.cmd`，默认访问 `http://127.0.0.1:7860`。可用 `Start.cmd -Port 7861` 指定其他端口。
4. 在 Web UI 的 resources 页配置 chat model 和 embedding model。生成模型的 API key 不等于 embedding 服务已配置。
5. 上传并索引 `samples/reviewer-note.txt`，选择该文档，询问项目 review marker，检查回答、引用和状态。文档中写明 `ORCHID-7429`；未提供 project manager，可用于观察证据不足的行为。这些提示不构成对任意模型输出的保证。

运行环境、配置、数据库、上传文件和日志位于解压目录的 `runtime` 中。`MARA.cmd` 提供同一环境中的 CLI。包内没有 API key、模型权重或预生成答案。首次安装访问 GitHub 和 PyPI；本包不是离线全量安装器。默认环境不安装可选的 `llama-cpp-python`，依赖安装采用 binary-only 模式，不要求评审自行编译它。

## 已验证的结果

测试宿主是现有 Windows x64 机器上的独立目录，不是全新 Windows 虚拟机。最终安装使用全新解压目录与独立缓存、环境，并将进程 PATH 限制为 Windows 系统目录，排除了已有 Python 和 Git。

| 检查 | 结果及范围 |
| --- | --- |
| 最终 ZIP 完整性 | 26 个清单文件 SHA-256 全部匹配；无额外未登记 payload，无 `.env`、`.git` 或已安装 runtime |
| 应用 wheel | 四个 wheel 均具备 Apache-2.0 元数据、LICENSE 和 NOTICE；ktem 内置资源与 PDF.js 内部校验通过 |
| 首次安装 | `Install.cmd` 退出 0，自动下载 Python 3.10.19，安装和依赖一致性检查通过，产生成功标记 |
| 空格路径 | 最终测试目录为 `D:\MARA-reviewer-tests\Final Review\MARA-reviewer-windows-x64-e6afa5dc` |
| 运行隔离 | 模块来自包内环境，config/data/cache 位于该包 `runtime/app` 下；未同步原开发环境 |
| CLI | `MARA --help`、`MARA.cmd app doctor --json`、`MARA.cmd docqa --help` 均退出 0 |
| Web 启动 | `Start.cmd -NoBrowser -Port 17860` 返回可访问的 HTTP 200；Computer Use 实际读取 chat 界面与内置帮助内容，版本显示 0.0.41 |
| 默认启动参数 | 重装后运行 `Start.cmd -Port 17860`，服务再次返回 HTTP 200。默认浏览器自动打开这一动作未单独获得视觉确认：Chrome 扩展枚举失败；前一项 UI 验证使用了内置浏览器 |
| 重复安装 | 退出 0，测试 `.env` 与数据文件的内容哈希均保持不变，成功标记有效 |
| 文件损坏 | 在另一份全新解压件中改变示例文件后，安装退出 1，明确报告 checksum mismatch，未产生成功标记 |
| 清理 | 测试服务进程已按实际程序路径和端口核对后停止；未停止其他 MARA 服务 |

真实模型问答尚未执行。`doctor` 的 `ok: true` 证明运行时可初始化，不能证明默认列出的 Google 模型有有效密钥，也不能证明生成、embedding、视觉或图路线可用。

## 构建期间修复与回归检查

新增 ZIP 构建器、锁定依赖预构建脚本、CMD/PowerShell 安装与启动脚本，以及独立运行目录入口 `MARA_APP_HOME`。保留现有 MARA/MARA-cli 命令及未设置该变量时的默认路径行为。

实际安装发现从 PowerShell 7 启动 Windows PowerShell 5.1 时，继承的模块路径会使 `Get-FileHash` 不可用；CMD 入口现在仅对本进程使用 Windows PowerShell 自带模块目录。

实际启动发现帮助页同步等待远程文档且无超时，导致服务迟迟不监听。帮助页现优先读取包内 Markdown，远程请求具有连接/读取超时，评审脚本默认关闭远程帮助更新。另修复 release note 缓存文件名使用错误变量的问题。相关修复先有失败回归，再通过验证。

| 开发验证 | 结果 |
| --- | --- |
| 新安装包/运行目录测试 | 8 passed |
| CLI 契约与既有运行路径测试 | 15 passed |
| `libs/slide_cli` 包级 gate | 退出 0 |
| 帮助页与运行路径回归 | 10 passed；其中新增的 4 项帮助页回归在修复前失败 |
| app CLI/init/NLTK 定向测试 | 41 passed，4 failed |
| 未修改 main 的失败项对照 | 同样 4 failed：Windows 无 `os.mkfifo`，以及本机无符号链接创建权限的三项 fixture；并非此次新增回归 |
| pre-commit / hygiene | 修改的 Python 文件适用检查通过；没有更新 hygiene baseline |
| PowerShell 语法 | 所有 4 个 `.ps1` 通过解析检查 |

不能把上述结果表述为“整个仓库所有测试通过”。本次没有开展新的 QA benchmark，也没有更改路由与回答算法。

## 后续边界

- 对外发布前，建议用计划支持的真实 chat 和 embedding 服务执行示例文档的索引、问答与引用检查；视觉/图路线需另配对应后端。
- 本包仅针对 Windows x64。本次没有验证 macOS、Linux、ARM64、全新 Windows VM 或受限企业网络。
- 页面在较窄视口仍有既有布局拥挤；帮助页在含空格路径下有部分图片 Markdown 未正确渲染，文字步骤可读。这些 UI 完善项尚未处理。
- `pypdf` 弃用提示和 Gradio 下拉框默认值提示仍存在，本次启动未因此失败。
- 本次只交付本地安装 ZIP。EACL 投稿表需要可公开访问的下载地址；上传到合适的 GitHub Release 并复测公开下载链路后，才能将那个地址填写为新安装包链接。旧 v0.0.40 release 链接目前不会自动指向本包。
- 基于 Git clone 的源码安装路线属于后续工作，本次没有将其记录为完成。

## 可追溯材料

构建与完整日志保存在 `D:\MARA-reviewer-build\20260923-main-dfcca998`。关键材料包括：

- `final-bundle-integrity.json`、`final-wheel-checks.json`、`final-startup-checks.json`。
- `final-repeat-install.json`、`final-tamper-check.json`。
- `logs/final-zip-install3.log`、`logs/final-app-doctor.log`、`logs/final-docqa-help.log`。
- `logs/final-bundle-server.log`、`logs/final-default-start.log`。
- `logs/final-repeat-install.log`、`logs/final-tamper-check.log`。
- `logs/cli-package-gate.log`、`logs/cli-path-contracts.log`、`logs/help-regressions-before.log`、`logs/help-regressions-after.log`。
- `logs/app-regressions.log`、`logs/main-baseline-platform.log`、`logs/precommit-final.log`、`logs/help-precommit.log`。

重建方法见 [reviewer_installation.md](reviewer_installation.md)。向评审分发时使用未安装过的 ZIP，而不是包含测试配置的解压目录。
