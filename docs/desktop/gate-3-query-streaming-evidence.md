# MARA Desktop Gate 3 真实问答纵向切片证据

## 结论

整改提交 `2464ed1337cb8cb509639122a5a7a25798948415` 关闭了审查提出的八项 P1，
`06fd7a456d1c4cf4981902d0ccb248b3a0c0d32e` 又消除了 Windows 低时钟分辨率下的
任务保留顺序不确定性。最终分支提交 `5436e614ac3ad785e3dc70732b5626aa49f61fcc`
同时修复了 GitHub runner 使用真实 `.venv` 目录时的基准契约测试。

[Desktop 运行 31323902842](https://github.com/262412/MARA/actions/runs/31323902842)
已 3/3 成功：Windows Server 2022 和 Ubuntu 22.04 原生打包及完整 smoke 通过，
Ubuntu 24.04 对 Ubuntu 22.04 同一包和同一数据快照复验通过；Windows Defender 为
`scan_result=no_detections`。

[Quality gates 31324140613](https://github.com/262412/MARA/actions/runs/31324140613)
对应最终分支提交，已 20/20 成功，覆盖完整 Python/CLI、前端安全、覆盖率、静态与
代码卫生、依赖审计、秘密扫描、干净 wheel 安装和三类容器供应链任务。

本轮问答切片的自动化整改已经闭环，但功能矩阵和整个 Gate 3 仍为 **In progress**。
当前包尚未在 Windows 10/11 产品 VM 复验；页级/选中文本范围、“全部/本次上传”来源
模式、建议问题、可公开推理阶段、引用点击跳页/高亮，以及 Preview、Notes、Studio、
Knowledge Graph、完整 Resources 资源管理、完整 Settings 分组和迁移等 P0 能力也尚未
关闭。基础 Resources/Help/Settings 页面、离线帮助、独立 Chat/Embedding 设置和
问答准备状态已在后续切片实现，证据见
[草稿、导航与模型准备纵向切片](gate-3-draft-navigation-and-model-settings-evidence.md)。

## 2026-08-09 NO-GO 整改闭环

| 审查问题              | 当前处理与回归证据                                                                                                 |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 跨文件引用身份        | 去重键包含文件 ID；稳定 citation ID 同时哈希文件和 evidence identity；文件名只允许精确且唯一别名，歧义失败关闭     |
| 阻塞流取消            | 取消信号传入共享 `DocQARuntime`；生产线程与单任务 executor 解耦；阻塞流不再阻止任务进入 `cancelled` 或后续任务运行 |
| Renderer 状态倒退     | 同一任务按 `version` 单调合并；重试 lineage 显式替代父任务；延迟 latest/父任务事件不能覆盖新任务                   |
| watcher 永久退出      | healthy 状态下对临时 SSE/GET 失败执行 250 ms 至 5 s 的有界退避，只在终态、不可重试失败或 Sidecar 不健康时退出      |
| CSS 块未闭合          | 修复 Sources checkbox 规则，并以关键选择器和括号平衡回归锁定生产样式                                               |
| 来源上限漂移          | Sidecar request/response model、OpenAPI 和 Electron IPC 统一为 1–64，第 65 个来源在 API 与 IPC 层失败              |
| 重试幂等混淆          | 幂等指纹绑定操作类型和目标任务；先验证目标存在，再重放同一请求；冲突 key 返回 409                                  |
| Composer/partial 回退 | prompt 只在观察到新 task ID 时清空一次；重试初始快照保留取消任务的 partial 与 citations                            |
| P2 预校验与 journal   | 会话/文件在返回 202 前验证；token 更新最多每 250 ms 合并落盘，终态强制写入，并只保留最近 100 个任务                |

真实组合包使用 `report.txt` 与 `report.txt.bak.txt` 两个内容不同、名称相似的文件。
共享 runtime 的 references bridge 对两条引用使用相同 `evidence_id=citation-refs`，因此该
E2E 实际覆盖跨文件 evidence ID 碰撞；最终任务必须同时返回两个不同、安全的 citation
ID，并保持 `qa_scope=multi_document`，否则应用以非零状态退出。

## 当前可下载预览包

[GitHub Pre-release `desktop-gate3-preview-06fd7a4`](https://github.com/262412/MARA/releases/tag/desktop-gate3-preview-06fd7a4)
提供无需安装 Python/Node.js 的 Windows x64 ZIP、Linux x64 TAR.GZ 和 SHA-256 清单。
发布前已重新测试两个压缩包的完整性并校验清单：

| 资产                                          | 大小              | SHA-256                                                            |
| --------------------------------------------- | ----------------- | ------------------------------------------------------------------ |
| `MARA-Desktop-Gate3-06fd7a4-Windows-x64.zip`  | 403,113,301 bytes | `ee0aac84142a935abab090d4121d6d004f65e861bff877f2fd978f4bbe51cb8a` |
| `MARA-Desktop-Gate3-06fd7a4-Linux-x64.tar.gz` | 429,675,004 bytes | `e3b2442cd2e182cc8bc07d78491ab5c9e58d7ba039735eeb39aeff14b1763eda` |

上一版 `desktop-gate3-preview-2878e81` 已转为 Draft，保留审计资产但不再作为公开下载。

## 历史基线：沙箱 Preload 发布修复

首次公开的 `ce5816e` 预览包存在发布阻断缺陷：TypeScript 产出的 Preload 保留
`require("./dropped-file-import")`，Electron sandbox loader 因而拒绝加载整个脚本。
真实页面中 `window.desktop` 为 `undefined`，Doctor、Files、Sessions、导入和问答均
进入“仅能在 MARA Desktop 中使用”的浏览器降级分支。此前组合包 smoke 直接从 Main
访问 Sidecar，未覆盖 Renderer → Preload → IPC，所以没有捕获该问题。

修复提交 `2878e815a55970201136c4dc8817ad9a4ca53883` 使用现有 Vite 构建器把 Preload
及本地辅助模块输出为一个 CommonJS 文件，唯一外置模块为 `electron`；
`sandbox: true`、`contextIsolation: true` 和 `nodeIntegration: false` 均由回归测试锁定。
每次开发态和打包 smoke 现在都从 Renderer 主世界验证完整桥接并真实调用 Runtime、
Doctor、Files 和 Sessions IPC，成功标记为：

```text
renderer_bridge=window.desktop real_ipc=runtime,doctor,files,sessions status_success
```

[Desktop 运行 31311652117](https://github.com/262412/MARA/actions/runs/31311652117)
已 3/3 成功：Windows 每个组合 smoke、Ubuntu 22.04 主/故障 smoke 和 Ubuntu 24.04
跨版本复验均输出该标记；Defender 为 `scan_result=no_detections`。
[Quality gates 31311652197](https://github.com/262412/MARA/actions/runs/31311652197)
已 20/20 成功。

| artifact                        | ID           | Actions digest                                                     |
| ------------------------------- | ------------ | ------------------------------------------------------------------ |
| `mara-desktop-windows`          | `9037631862` | `6b0a00fb26a8627a1a5478e818981dd76aa20daf071345ca4a10be761eba0420` |
| `mara-desktop-linux-22`         | `9037625142` | `831f3a20539719bca9132274c94a7603f6889fc51bc345cd323d07500d6041b5` |
| `mara-desktop-windows-defender` | `9037625132` | `966d3eb9c337139377e7d496a01c690d13f103820610bad3007622499762a0da` |

上一版 `desktop-gate3-preview-2878e81` 曾提供 Windows x64 ZIP、Linux x64 TAR.GZ
和 SHA-256 清单。发布资产校验值分别为
`330b284620a12152833e97bb128786d476157991a54c04d1fc7a157617cfba4a` 和
`f8eb89c61324f61073afa847d4e26956548724bb851d17a78233f68b16a64eb7`。
旧 `desktop-gate3-preview-ce5816e` 已转回 Draft，保留审计资产但不再公开下载。

## 公共表面与复用边界

- Sidecar 版本提升到 `0.7.0`，增加 `query_stream`、`query_cancel` 和 `query_retry`
  capabilities，以及认证后的创建、读取、最新任务、SSE、取消和重试端点。
- 创建只接受会话 ID、1–20,000 字符 prompt 和 1–64 个唯一文件 ID，并要求
  idempotency key。额外字段、查询参数、错误 Origin、未认证请求和非法 ID 均失败
  关闭；重试使用新的 idempotency key，但范围只能复制原任务。
- application service 在 owner-scoped 会话和当前脱敏 Files 记录中验证来源，再调用
  `DocQARuntime.stream_turn()`。单文件使用 `document`，多文件使用
  `multi_document`，固定现有 `simple` reasoning 与 inline citation；没有调用 Click
  命令、复制 Gradio callback 或另写检索/生成逻辑。
- Desktop 通过 `source_identity_crosswalk` 把 runtime evidence 映射回本次已选文件。
  Renderer 只收到 citation ID、文件 ID、文件名、可选页码/元素 ID 和证据文本；未知
  metadata、用户 ID、数据库字段和本地路径不会被投影。
- OpenAPI 生成完整 Query task 与 citation TypeScript 类型并检查漂移。Preload 只增加
  `desktop.submitQuestion()`、`getLatestAnswerTask()`、`cancelAnswer()`、
  `retryAnswer()` 和 `onAnswerTaskStatus()`；Main 再次验证 sender 和精确参数。
- Renderer 不接收 Sidecar URL、端口、令牌、模型参数或凭据。Sources 面板只选择真实
  indexed Files；Composer 覆盖禁用原因、排队、检索/生成、success、failed、
  cancelled、partial、停止和重试状态。
- 问答 journal 位于独立 Desktop 数据根并原子替换。进程重启时 queued/running 任务
  转为可重试 `query_interrupted`；最新任务由 Main 恢复并重新投影到 Renderer。

## 行为保护与本地验证

Desktop 没有修改 `MARA` / `MARA-cli` 命令、Click 参数、Gradio 事件链、Conversation
schema 或已有 `data_source` 形状。`create_docqa_runtime()` 新增参数都有保持现有默认值
的兼容覆盖，完整 `libs/slide_cli/tests` 通过；`libs/kotaemon` 全套测试为 365 passed、
10 skipped。

内联引用特征测试还锁定一个共享 DocQA 修复：claim verification 在比较数字前去掉
`【1】` 等引用标记，避免把引用序号或 `gate3-...` 文件名误当成事实数字而错误
abstain；真实年份冲突仍会失败。

| 层级                            | 结果                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| Web/CLI 与共享 DocQA            | 共享 runtime 取消特征测试 4 passed；最终 Quality 全套验证                          |
| Application service             | 真实 stream、owner 会话、预校验、碰撞/歧义引用 crosswalk 通过                      |
| Sidecar                         | 70 passed；认证、64 来源、幂等、SSE、阻塞取消、journal 上限、稳定失败和路径脱敏    |
| OpenAPI → TypeScript 漂移检查   | 通过                                                                               |
| Electron Main/Preload           | 56 passed；明确 IPC、sender、64 来源、watch 重连、恢复和双文件组合包断言           |
| React                           | 18 passed；来源四态、单调任务状态、重复 prompt、partial 重试保留和 CSS 结构        |
| 打包配置                        | 3 passed；包含 `simple` reasoning、OpenAI chat 和延迟加载子模块                    |
| 代码卫生与格式                  | pre-commit、mypy 和 codebase hygiene 通过；baseline 未扩大或刷新                   |
| TypeScript 与生产 Renderer 构建 | 通过                                                                               |
| 本地 Linux 组合包 smoke         | 真实双文件索引 → 两个安全引用 → partial 取消 → 原范围重试 → 清理通过；`ldd` 无缺失 |

本地冻结包第一次复验发现 PyInstaller 未自动收集
`ktem.reasoning.prompt_optimization.decompose_question`；加入明确隐藏模块并删除当前
Chroma 版本中不存在的旧隐藏模块后重新打包成功。本轮本地 Linux 包为
1,088,484,376 bytes、2,072 个文件，Sidecar `ldd` 无缺失，并输出：

```text
renderer_bridge=window.desktop real_ipc=runtime,doctor,files,sessions status_success
gate3_query=real_multi_document_grounded_citations status_success
gate3_query_cancel=partial_preserved retry=status_success
```

## 跨平台组合包证据

最终三平台任务都输出 Renderer bridge、真实双文件引用和 partial 取消/重试标记。
第一个业务标记要求两个文件真实完成索引、答案经共享 runtime 持久化到真实会话、
`qa_scope` 为 `multi_document`，且每个来源各有一个不同的安全 citation ID；第二个标记
要求回答已经产生 partial、取消后保留内容、重试复制同一会话/prompt/两个文件范围并最终
成功持久化。任一条件失败都会让组合包进程非零退出。

当前 artifact 均未过期，到期时间为 2026-11-07：

| artifact                                 | ID           | 上传大小    | Actions digest                                                     |
| ---------------------------------------- | ------------ | ----------- | ------------------------------------------------------------------ |
| `mara-desktop-windows`                   | `9041064925` | 410,600,053 | `25fa19ac334130993917725fae586f4492e7f8337dd7ce9457d8020a28818297` |
| `mara-desktop-windows-defender`          | `9041057871` | 357         | `c606bd1690788702d25b7fa53c5ef9d51b57459296b42ce5a536c24421452086` |
| `mara-desktop-windows-smoke-diagnostics` | `9041057660` | 6,903       | `3d4f6e2e8fd467696674f48c01caaa5be0c17a3476b46c4f0a59a916ad557d1f` |
| `mara-desktop-linux-22`                  | `9041056072` | 427,647,595 | `e7652b2029bdcf1bf7e208db26d41d9174e139134f55fbbfde6318ebb15dfce2` |
| `mara-desktop-linux-22-metrics`          | `9041056275` | 8,053       | `be27ecf5db5a2c328e706b6f081f8a159745134d529dc38ec41cb701671e8584` |

| 指标                   | Windows Server 2022                                                | Ubuntu 22.04                                                       |
| ---------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 发布目录 apparent size | 1,016,648,229 bytes                                                | 1,105,389,837 bytes                                                |
| 发布目录文件数         | 2,741                                                              | 2,142                                                              |
| 主组合 smoke           | 18.176 秒                                                          | 14.68 秒                                                           |
| 主组合 smoke 峰值内存  | 101,756,928 bytes                                                  | 543,984 KiB                                                        |
| Sidecar SHA-256        | `e85b5dff107635630f4201701b3021ec80ad05cfdc870c69a979d8dc99423191` | `2da41b40a5fc951d333a81a17391bfa6051b8a4ec546bba002f176b19fd9fb59` |
| 原生/安全结果          | 全部问答/故障 smoke 通过；Defender 无检出                          | `ldd` 无缺失；全部问答/故障 smoke 通过                             |

Defender 诊断还确认引擎和 antimalware service 开启、归档扫描开启，并在扫描前移除了
runner 的 `D:\` 整盘排除。Ubuntu 24.04 没有重新构建，而是下载 Ubuntu 22.04 的同一
artifact 与数据快照进行 smoke，保留了 glibc 最低基线的实际意义。

## 剩余验收与下一切片

1. 在 Windows 10 和 Windows 11 产品 VM 上使用 artifact `9041064925` 或本轮
   Pre-release 复验单/多文件
   提问、键盘发送/停止、partial、重试、重启恢复、Defender 和退出后残留进程。
2. 增加“全部来源/本次上传”、页级和选中文本范围，并为四种 QA scope 取得共享 runtime、
   Sidecar、IPC、React 和打包 E2E 证据。
3. 把引用列表升级为可聚焦操作；点击后打开 Preview、跳到页/元素并高亮证据，同时覆盖
   同名多文档身份。当前切片只证明安全身份和文本展示，不声称定位 UI 已完成。
4. 完成建议问题和可公开检索/推理阶段事件；不得把模型私有思维链暴露到 Renderer。
5. 当前冻结包会记录未打包可选 Web search backend 的导入警告，但 Desktop 不暴露该
   能力且 `simple` 问答成功。后续来源/模型切片应显式关闭或完整打包所选后端，避免
   启动日志噪声。
6. GitHub-hosted runner 会提示部分固定版本 action 仍以 Node 20 为目标、由平台强制
   运行于 Node 24。当前供应链策略与任务均通过；后续维护切片应审计并升级 allowlist，
   不能改用浮动 action 标签。
7. Gate 3 只有在功能矩阵全部 P0 能力取得自动化或人工验收证据后才能关闭；当前总体
   状态继续为 **In progress**。
