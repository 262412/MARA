# MARA Desktop Gate 3 真实问答纵向切片证据

## 结论

功能提交 `7d6ed9afc6cf2707419e1660437c8ddbc045dd10` 已把真实文档/多文档问答贯通
React、Preload、Electron Main、认证 Sidecar 与现有 `DocQARuntime.stream_turn()`。
修复提交 `27b6c5d74040755015dafc39b25350982a50f4d7` 关闭了跨版本 smoke 数据快照中
持久化模型端点与随机测试端口不一致的问题。

[Desktop 运行 31290067911](https://github.com/262412/MARA/actions/runs/31290067911)
已 3/3 成功：Windows Server 2022 和 Ubuntu 22.04 原生打包、真实问答 smoke 通过，
Ubuntu 24.04 对 Ubuntu 22.04 同一包和同一数据快照的复验也通过；Windows Defender
得到 `scan_result=no_detections`。

[Quality gates 31290067977](https://github.com/262412/MARA/actions/runs/31290067977)
已 20/20 成功，包含完整 Python/CLI、前端安全、覆盖率、静态与代码卫生、依赖审计、
秘密扫描、干净 wheel 安装和三类容器供应链任务。

本能力和整个 Gate 3 仍为 **In progress**。当前切片没有完成页级/选中文本范围、
“全部/本次上传”来源模式、建议问题、公开推理轨迹、引用点击跳页/高亮，也尚未在
Windows 10/11 产品 VM 上复验。Preview、Notes、Studio、Knowledge Graph、Resources、
Settings、Help 和迁移等 P0 能力同样未关闭。

## 2026-08-09 沙箱 Preload 发布修复

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

[修复版 GitHub Pre-release](https://github.com/262412/MARA/releases/tag/desktop-gate3-preview-2878e81)
提供 Windows x64 ZIP、Linux x64 TAR.GZ 和 SHA-256 清单。发布资产校验值分别为
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

| 层级                            | 结果                                                            |
| ------------------------------- | --------------------------------------------------------------- |
| Web/CLI 与共享 DocQA            | `slide_cli` 全套通过；`kotaemon` 365 passed、10 skipped         |
| Application service             | 真实 stream、owner 会话、单/多文件范围和安全引用 crosswalk 通过 |
| Sidecar                         | 64 passed；认证、参数、幂等、SSE、journal、稳定失败和路径脱敏   |
| OpenAPI → TypeScript 漂移检查   | 通过                                                            |
| Electron Main/Preload           | 48 passed；明确 IPC、sender、范围、SSE、恢复和组合包断言        |
| React                           | 13 passed；来源四态、流式/success/failed/cancelled 与禁用原因   |
| 打包配置                        | 3 passed；包含 `simple` reasoning、OpenAI chat 和延迟加载子模块 |
| 工作流、供应链与卫生测试        | 45 passed；hygiene baseline 未扩大或刷新                        |
| TypeScript 与生产 Renderer 构建 | 通过                                                            |
| 本地开发态和 Linux 组合包 smoke | 真实索引 → 流式回答/引用 → partial 取消 → 原范围重试 → 清理通过 |

本地冻结包第一次复验发现 PyInstaller 未自动收集
`ktem.reasoning.prompt_optimization.decompose_question`；加入明确隐藏模块并删除当前
Chroma 版本中不存在的旧隐藏模块后重新打包成功。最终本地 Linux 包约 1.1 GiB、2,072
个文件，Sidecar `ldd` 无缺失，并输出：

```text
gate3_query=streaming_grounded_citations status_success
gate3_query_cancel=partial_preserved retry=status_success
```

## 跨平台组合包证据

最终三平台任务都输出上述两个标记。第一个标记要求真实文件完成索引、答案经共享
runtime 持久化到真实会话，并至少返回一个指向所选安全文件 ID 的引用；第二个标记
要求第二次回答已经产生 partial、取消后保留内容、重试复制同一会话/prompt/文件范围，
并最终成功持久化。任一条件失败都会让组合包进程非零退出。

首次运行
[31289602212](https://github.com/262412/MARA/actions/runs/31289602212) 的 Windows 和
Ubuntu 22.04 已通过，但 Ubuntu 24.04 复用数据快照时因数据库持久化了 Ubuntu 22.04
随机 smoke 模型端口而请求旧端点，得到 `RetryError`。修复只让 CI 辅助模型服务器在
两个隔离 runner 上使用同一确定性 loopback 端口；产品 Sidecar 的随机端口和强令牌
边界未改变。最终 Ubuntu 24.04 在 38 秒任务内通过同一快照复验。

当前 artifact 均未过期，到期时间为 2026-11-07：

| artifact                                 | ID           | 上传大小    | Actions digest                                                     |
| ---------------------------------------- | ------------ | ----------- | ------------------------------------------------------------------ |
| `mara-desktop-windows`                   | `9031157175` | 410,591,865 | `e7ed959435f46c2caf5bea3d839fd0d859d1ef90868ddd7b2398164cf4175f97` |
| `mara-desktop-windows-defender`          | `9031151171` | 358         | `9af8aab1c2a4048e33551ea880e7284f13d1d6720e1b72aadfc4a468b6c31c0c` |
| `mara-desktop-windows-smoke-diagnostics` | `9031151069` | 6,475       | `ad87f9d4509a1812427ca24cb88924abaca1dc6b8463b93f6b19ac2f9f80d048` |
| `mara-desktop-linux-22`                  | `9031153124` | 427,596,457 | `e22b8279ad6190e5adba01f1b6c2d6ec2d9d247884d74cdf72bd6c5f43d1e905` |
| `mara-desktop-linux-22-metrics`          | `9031153257` | 7,829       | `27772e7d3410f7fade903555be9576b8e803f2bfd8911bde7ea6104ea1d69792` |

| 指标                   | Windows Server 2022                                                | Ubuntu 22.04                                                       |
| ---------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 发布目录 apparent size | 1,016,629,163 bytes                                                | 1,105,371,163 bytes                                                |
| 发布目录文件数         | 2,741                                                              | 2,142                                                              |
| 主组合 smoke           | 16.862 秒                                                          | 16.89 秒                                                           |
| 主组合 smoke 峰值内存  | 100,155,392 bytes                                                  | 538,524 KiB                                                        |
| Sidecar SHA-256        | `62b4898e336df3454e4b5b76f941b1af7b9351392fce1dbbcd37f2a385bbb5c7` | `7f1f82d7d7b8a5bf5e81904c7a1c49cfbcfbaab7b3bfcc70ab8a19faeca1fefb` |
| 原生/安全结果          | 启动、问答、故障 smoke 通过；Defender 无检出                       | `ldd` 无缺失；问答和全部故障 smoke 通过                            |

## 剩余验收与下一切片

1. 在 Windows 10 和 Windows 11 产品 VM 上使用 artifact `9037631862` 或修复版
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
