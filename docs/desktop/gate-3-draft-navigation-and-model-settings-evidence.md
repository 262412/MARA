# MARA Desktop Gate 3 草稿、导航与模型准备纵向切片证据

## 2026-08-12 模型路由一致性与凭据清理结论

实现提交 `03b78e807720d3b877642b6b9867c4f6363a558a` 把 Electron 当前模型设置设为
Desktop 唯一路由权威，增加旧模型表与
embedding 表的版本化幂等迁移、安全凭据清理、精确 settings revision 握手、实际 route
诊断和 provider 错误分类。使用旧 Google 默认、同名旧 Ollama/OpenAI route、多默认项
及旧 Azure embedding 的数据根启动后，Settings、Doctor、SQLite 非敏感投影、运行时
manager、查询任务和实际流式 POST 均收敛到当前设置。

当前本地 Linux 原生组合包已从系统只读工作目录完成真实 loopback 查询，捕获到
`{"model":"gpt-5.6-luna","stream":true}`；SQLite、WAL/journal、Desktop 数据根、
日志和 smoke 诊断均未检出旧明文凭据 sentinel，仓库根、工作目录与安装目录均未产生
`.theflow`。该结果只证明当前 Linux 构建，不能替代 Windows 产品验收。

正式结论仍为 **NO-GO**，能力保持 **In progress**：当前源码还必须取得 Windows
Server 2022 原生构建/loopback/Defender 证据，并在干净 Windows 10 与 Windows 11
产品 VM 验证同一用户重启、覆盖安装、卸载后重装、safeStorage、旧数据库迁移和实际
POST route。任一平台设置模型与实际 POST 不一致都阻止放行。

## 历史基线结论（70a7021）

实现提交 `c0d952a1e482ff9c57202f2bc970ffdcf826840b` 修复了冷启动会话、占位导航、
模型设置与问答准备四组相互关联的用户级缺陷；提交
`70a70216892ce92c4f3828fde461a094819dc254` 只修正 Windows 打包 smoke 使用的
应用数据根。两个提交都直接位于 `Dev`，没有创建或使用其他开发分支。

[Desktop Gate 2/3 运行 31496464841](https://github.com/262412/MARA/actions/runs/31496464841)
对应 `70a7021`，三个原生任务全部成功：Windows Server 2022 原生构建、组合包 smoke
和 Defender 扫描通过；Ubuntu 22.04 原生构建与 smoke 通过；Ubuntu 24.04 使用同一
Ubuntu 22.04 包跨版本复验通过。

本纵向切片的代码、自动化和托管 runner 验收通过，但正式结论仍为 **NO-GO**，Gate 3
保持 **In progress**：

1. 当前源码包尚未在干净 Windows 10 和 Windows 11 产品 VM 复验安全存储、首次/
   重复启动、真实模型、退出进程和 Defender 行为。
2. 125%/150% Windows 缩放和真实中文 IME 仍需要产品环境人工验收。
3. [Quality gates 31496465192](https://github.com/262412/MARA/actions/runs/31496465192)
   的三个 Python dependency-audit profile 发现共享依赖 `pypdf==4.2.0` 新增
   `PYSEC-2026-3655` 和 `PYSEC-2026-3656`。修复版本要求跨越 Kotaemon 当前
   `pypdf>=4.2.0,<4.3` 公共依赖范围；本切片没有放宽门禁、刷新审计基线或擅自执行
   无关的主版本升级。

## 根因到修复的映射

| 用户级缺陷                       | 根因                                                                   | 当前修复与失败关闭行为                                                                                                       |
| -------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 启动即出现已保存会话             | 冷启动把历史会话选为活动任务，“新建”在发送前持久化空会话               | 启动和 `Ctrl/Cmd+N` 都进入本地可编辑草稿；只有第一次有效发送才幂等创建一个会话和一个问答任务                                 |
| 侧栏入口仍是占位行为             | 页面状态以非类型化占位分支复用工作台                                   | 导航固定为 `workbench/files/resources/help/settings`；每页有独立标题、ARIA 当前态和焦点目标，离线 Help 随包分发              |
| Chat 与 Embedding 无产品配置路径 | Desktop 依赖进程环境和含占位凭据的旧默认模型，无法独立表达两条路由     | 增加独立 OpenAI-compatible、Azure OpenAI、Ollama 或未配置路由；保存后受控重启 Sidecar，并以 Doctor 重新确认两类准备状态      |
| 未准备好仍创建问答任务           | Renderer 和 Sidecar 缺少结构化 query readiness，失败落入通用运行时错误 | Doctor 提供生成契约；Main 和 application service 在创建会话/任务前预检；配置缺失、依赖缺失和认证失败均不可盲目重试           |
| Composer 可能重复发送或破坏输入  | 键盘提交依赖浏览器默认行为，没有统一处理 IME、重复 keydown 和换行      | `Enter` 单次发送，`Alt+Enter` 在光标处插入一个换行，`Ctrl/Meta+Enter` 保持兼容；composition、key repeat 和快速重复提交被拦截 |

首次建会话或提交失败时，prompt、来源选择和草稿身份均保留。切换 Files、Resources、
Help 或 Settings 不取消后台问答；返回工作台后继续观察同一个任务。

## 公共表面与兼容边界

本切片只调整下列 Desktop-owned 表面：

- 新增共享 `model-contracts.ts`，并扩展 OpenAPI 生成的 Doctor 契约。
- Preload 增加明确的 `desktop.getModelSettings()` 和
  `desktop.saveModelSettings(settings)`；Main 逐方法校验 sender 和精确参数。
- Doctor 增加 `query_ready`、稳定 issue/message/action/retryable、Chat provider/model
  以及 Embedding provider/model 的非敏感投影。
- Renderer 增加五类强类型路由、三个真实页面、受控 Composer 和模型设置表单。
- Desktop runtime defaults 只在 `MARA_DESKTOP_MODEL_SETTINGS=1` 时采用独立的
  Chat/Embedding 路由；未设置该标记时保持 Web、CLI 和 Gradio 的旧行为。
- Doctor 和查询任务增加实际 route 的 provider/model、settings revision、Sidecar PID
  与 route fingerprint；这些字段由 OpenAPI 生成共享类型。

本切片没有修改 `MARA` / `MARA-cli` 命令、Click 参数、Gradio 事件链、DocQA 数据库
schema 或既有索引/问答任务字段语义；查询任务仅增加向后兼容的路由诊断字段。Renderer 仍不知道 Sidecar
端口、令牌或本地路径；没有增加通用 `invoke`、`request`、文件读写或任意 URL IPC。

## 模型设置与安全边界

- Chat 与 Embedding 使用互相独立的 provider、base URL 和 model；OpenAI-compatible
  与 Azure 路由需要凭据，Ollama 仅允许回环 HTTP，远程服务必须使用 HTTPS。
- `""`、`<YOUR_OPENAI_KEY>`、`your-key`、`your_api_key` 和 `your_key` 都被视为
  无效占位值，不能使 Doctor 进入 ready。
- 非敏感元数据原子写入 Desktop 数据根的 `state/model-settings.json`；凭据只写入
  Electron `safeStorage` 加密的独立文件，权限收紧为当前用户可读写。
- Linux 若 Electron 只能提供 `basic_text` 后端，则明确降级为当前进程会话凭据，不把
  凭据持久化。旧 `state/config/.env` 的受支持模型路由只迁移一次，随后移除模型变量并
  保留无关配置；升级用户应轮换曾由旧版本明文保存的 API key。
- Renderer 提交用户当前输入的凭据后只接收 `credential_present` 和
  `credential_storage`；Main/Sidecar 不把凭据值回传，日志和错误也不记录该值。
- SQLite 模型与 embedding spec 只保存非敏感 route 和 `secret_ref`；当前完整 spec 只在
  Sidecar 进程内由 Electron 解密值叠加。迁移会清理主库、WAL/journal 和 Desktop 备份，
  不删除会话、索引、文件或其他用户表。
- 保存设置会停止旧 Sidecar、以新 revision 环境启动一个 Sidecar，并等待 Health 与
  Doctor 的 revision/PID/fingerprint 全部一致；任何阶段失败都返回稳定、脱敏且带
  `request_id` 的错误。

## 问答准备与错误契约

Doctor 的 `query_ready` 是 Renderer 启用发送的唯一业务准备依据；UI 不解析英文警告
字符串。未准备好时不会创建空会话或 `query-tasks.json` 任务，并提供打开 Settings 的
明确动作。

| code                        | retryable | 用户动作                            |
| --------------------------- | --------- | ----------------------------------- |
| `llm_not_configured`        | false     | 配置 Chat 路由                      |
| `llm_credentials_missing`   | false     | 提供所选路由的凭据                  |
| `llm_authentication_failed` | false     | 检查或更新凭据                      |
| `llm_dependency_missing`    | false     | 修复安装包，不能盲目重试            |
| `llm_model_not_found`       | false     | 检查模型 ID 与 endpoint             |
| `llm_model_unsupported`     | false     | 选择 provider 支持的模型            |
| `llm_model_access_denied`   | false     | 检查账号的模型访问权限              |
| `llm_provider_unreachable`  | true      | 检查服务/网络后重试                 |
| `llm_rate_limited`          | true      | 等待后重试                          |
| `query_timeout`             | true      | 重试问答                            |
| `query_runtime_failed`      | false     | 记录 request/task ID 后诊断未知故障 |

`llm_dependency_missing` 只表示真实 Python import/package 缺失；provider 返回的 unknown、
not found 或 unsupported model 不再描述为“模型未包含在 MARA build”。Sidecar 维护者
日志写入 Desktop-owned 日志目录，只记录 request/task ID、稳定类别和异常类型；安全的
provider request ID 与状态/错误码可进入任务诊断，绝对源路径、API key、Sidecar
token/port、响应正文和 traceback 不进入 Renderer 响应。

## 回归与本地 Linux 证据

先添加失败回归，再修改生产代码。当前本地验证结果：

| 验证层                              | 结果                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------- |
| `cd apps/desktop && npm run verify` | Electron 75、Renderer 34、Sidecar 106、打包配置 5；契约漂移、类型和生产构建通过 |
| 受影响 `ktem` / `slide_cli` DocQA   | 105 passed；另有 9 项公共 CLI 契约通过                                          |
| workflow 与供应链策略               | 51 passed                                                                       |
| 代码卫生                            | 所有变更 Python 文件 pre-commit 与 hygiene gate 通过；baseline 未刷新           |
| Node 依赖                           | `npm audit` 为 0 vulnerabilities                                                |

本地 Linux 组合包从只读、非仓库工作目录启动。无模型配置时，真实打包 Renderer 输出：

```text
renderer_bridge=window.desktop real_ipc=runtime,doctor,files,sessions,model-settings status_success
renderer_ui=real-navigation,draft,settings,keyboard mode=blocked status_success
indexing_ready=false issue_code=embedding_not_configured retryable=false task_created=false
query_ready=false issue_code=llm_not_configured retryable=false task_created=false
```

随后通过真实 Settings 页面分别保存回环 Chat 与 Embedding 路由、受控重启 Sidecar，
清除常规模型环境变量后第二次启动仍完成 TXT 索引、多文档问答、会话变更和批量删除。
任务进度只写入 `<data-root>/cache/theflow`；工作目录 `/usr`、安装目录和仓库根均不存在
`.theflow`。路由迁移报告确认只有一个默认 Chat route 和一个默认 Embedding route，
`chat_model=gpt-5.6-luna`、任务终态为 `success`、明文凭据不存在。

| 本地 Linux 指标 | 结果                                                                                          |
| --------------- | --------------------------------------------------------------------------------------------- |
| 发布目录大小    | 1,088,655,442 bytes                                                                           |
| 文件数          | 2,072                                                                                         |
| Linux 压缩包    | 421,463,028 bytes；SHA-256 `191dcfb68419126e7f7554a397b5cfa5fead3a4217300d63897de0bf9694f6ee` |
| Sidecar SHA-256 | `49e8795c76115954655736dcb28e2bb26cc80b5ebb5fc9204fb39f8912347f92`                            |
| 动态链接        | `ldd` 无缺失                                                                                  |
| 退出清理        | 无残留 Sidecar 进程                                                                           |

## 历史原生组合包证据（70a7021，不作为本轮验收）

所有 artifact 均对应 `70a7021`、未过期，预计于 2026-11-09 过期：

| artifact                                 | ID           | 上传大小    | Actions digest                                                     |
| ---------------------------------------- | ------------ | ----------- | ------------------------------------------------------------------ |
| `mara-desktop-windows`                   | `9103469715` | 410,673,316 | `87a0620b34ddd215474901791d9f6628dbb57837f248cb51adbec8bbb4a3a8dd` |
| `mara-desktop-windows-defender`          | `9103447751` | 358         | `4236196da23f86ce04b66c3650e600aae24bd8c15d29ab7f69da1e341540b19c` |
| `mara-desktop-windows-smoke-diagnostics` | `9103447041` | 9,421       | `655c665fc38943941724885b114ad187bbc4a3b2527ba391a25af521743137c2` |
| `mara-desktop-linux-22-metrics`          | `9103431795` | 11,471      | `7818d8179bca6dbece3878a730123112874e3855bb927d5bd3e89acf8b98e1ec` |
| `mara-desktop-linux-22`                  | `9103431226` | 427,775,904 | `946f356672294b981a7de846d7ded3bb10651ec8dcf4f62105b97505aac4af03` |

| 指标            | Windows Server 2022                                                                      | Ubuntu 22.04                                                       |
| --------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| 发布目录大小    | 1,016,768,874 bytes                                                                      | 1,105,510,799 bytes                                                |
| 文件数          | 2,741                                                                                    | 2,142                                                              |
| 主 smoke        | 16.145 秒                                                                                | 12.91 秒                                                           |
| 峰值内存        | 100,745,216 bytes                                                                        | 544,832 KiB                                                        |
| Sidecar SHA-256 | `7fed4c9067aadd007c84edf70c02220847348312266c1bac235c482672af6635`                       | `186fee8e2b9cd1639d753cebf6cfe7ea5a1bf71036d25e7aa4f3b1c0a4d3065a` |
| 原生检查        | `MARA.exe` SHA-256 为 `6ba65681db30add62942d2ab41748fbd7f06b33ef629c38224479960b6ffa388` | `ldd` 无缺失                                                       |

两个原生平台都完成以下真实打包行为：

- 冷启动进入可编辑草稿，页面导航、标题、焦点与键盘事件通过真实 Renderer。
- 无配置时同时返回 `embedding_not_configured` 和 `llm_not_configured`，且两个
  `task_created` 都为 false。
- Settings UI 保存独立回环路由、Sidecar 重启、Doctor ready 和脱敏状态通过。
- 第二次启动不依赖标准 provider 环境变量，真实索引、问答、取消/重试和删除通过。
- 故障、retry、cancel、partial、Sidecar 重启、磁盘满、数据库锁和 5 MiB canary 均以
  退出码 0 完成诊断断言。

Windows Defender 证据确认 antivirus 与 antimalware service 开启、移除 runner 的
`D:\` 整盘排除、archive scanning 开启，结果为 `scan_result=no_detections`。Ubuntu
24.04 下载 Ubuntu 22.04 的同一个 artifact 和数据快照复验，未用重新构建掩盖 glibc
基线。

## 残余风险与关闭条件

1. 在干净 Windows 10 和 Windows 11 x64 VM 上下载 artifact `9103469715`，记录 OS
   build、压缩包与可执行文件 SHA-256、100%/125%/150% 缩放、中文 IME、安全存储、
   首次/重复启动、真实远程或本地服务、Defender、数据根和退出后进程。
2. 单独升级并验证共享 PDF 栈，关闭 `PYSEC-2026-3655`、`PYSEC-2026-3656`，不得把
   新发现简单加入审计基线。
3. 完成 Resources 的 Index/Reranking/MCP/用户管理和 Settings 的设备、数据、外观、
   高级分组；当前证据只覆盖真实页面骨架、模型路由和本地帮助。
4. Gate 3 其余 Preview、Notes、Studio、知识图谱、导出和迁移 P0 仍按功能矩阵逐切片
   验收。本文件不把当前纵向切片通过解释为 Gate 3 完成。
