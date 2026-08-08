# MARA Desktop Gate 3 文件索引纵向切片证据

## 结论

Gate 3 的首个纵向切片是“原生文件导入 → 后台索引 → Files 刷新/删除”。实现已
贯通 React、Preload、Electron Main、认证 Sidecar 和现有 MARA DocQA runtime，
当前状态为 **In progress**。只有 Windows、Ubuntu 原生组合包均完成真实索引/删除
smoke，并补齐产品 VM、支持格式与异常场景验收后，才能升级为 `Verified`。提交
`fce9843` 已关闭 Windows Server 2022、Ubuntu 22.04/24.04 的轻量格式矩阵自动化
缺口；剩余项不再包含原生构建流水线或文本类格式的跨平台 smoke。

本切片不复制 Gradio callback 或 DocQA 索引/删除业务逻辑，也不修改 `MARA`、
`MARA-cli` 命令、Click 参数、Gradio 事件链、数据库 schema 或现有会话字段。

## 公共表面与安全边界

- Main 通过原生选择器取得文件路径；Renderer 只调用 `desktop.importFiles()`，
  不提供路径、选择器参数或任意文件读取能力。
- Main 通过认证 Sidecar 的 `/v1/import-capabilities` 读取当前 FileIndex 支持扩展名，
  原生选择器不再维护一份手写格式清单；空列表或畸形扩展会失败关闭。
- Preload 新增明确的 `getLatestIndexTask`、`cancelIndexTask`、
  `retryIndexTask`、`deleteFile` 和 `onIndexTaskStatus`；没有通用
  `invoke`、`request` 或 `readFile`。
- Sidecar 新增版本化索引任务、SSE 事件和单文件删除端点。所有端点继续执行
  Bearer 认证、Origin 拒绝、请求 ID、参数校验和稳定错误契约。
- 可重试写操作使用 idempotency key。Renderer 可见数据只包含任务 ID、文件名、
  计数、状态和脱敏错误，不包含导入路径或 Sidecar 端口/令牌。
- 索引任务日志保存在独立 Desktop 数据根；启动时把未完成任务标记为
  `index_interrupted`，用户可以重试失败或未完成文件。

## 业务逻辑复用

Desktop application service 延迟创建现有 `DocQARuntime`，索引直接调用
`index_paths()`，删除直接调用 `delete_files()`。删除继续由现有
`DeletionCoordinator` 处理关系记录、向量索引、数据库记录和受管文件，不在
Desktop 中复制另一套 DocQA 实现。

Desktop 的仅索引 runtime 不注册问答 reasoning 和 Web Search backend，避免把
本切片不使用的查询组件装入 Sidecar，也不发布尚未由 Desktop 暴露的文件导出
artifact。artifact 安全层在不支持 POSIX `dir_fd` 的平台会 fail-closed，不能为
Windows 添加普通路径回退；后续 Studio/导出切片必须先实现等价的安全句柄后端。
`create_docqa_runtime()` 默认仍注册完整查询与 artifact 能力，CLI 和 Web 路径保持
原行为。

新增的 CLI 特征测试锁定 `MARA docqa index` 与 `MARA-cli docqa index` 的路径、
`--reindex`、JSON 输出和部分失败退出码，防止 application service 复用过程中
改变已有命令行为。

## 自动化与 smoke

- Sidecar：索引/删除 application service、认证、参数、响应、idempotency、SSE、
  取消、部分失败重试、重启恢复和路径脱敏。
- Electron：原生选择器所有权、窄 IPC sender/参数验证、Sidecar 请求和 SSE 解析、
  打包 smoke 的失败退出码。
- React：loading、success、empty、failed，以及 queued、running、partial、
  success、failed、cancelled、取消、重试和删除中状态。
- OpenAPI 继续生成 checked-in TypeScript 契约，`npm run contracts:check` 检查漂移。
- 支持格式能力契约覆盖 application service、认证 Sidecar、OpenAPI、Main 原生过滤器
  和打包 smoke；真实内容矩阵仍按格式逐项验收，能力声明不等于格式已 Verified。
- `--smoke-test-gate3` 在独立数据根预置 Gate 2 非空数据，再创建一个真实文本索引
  任务，验证 Files 中出现脱敏记录，删除预置和新建记录，最后验证列表为空。
- `--smoke-test-gate3-formats` 在同一真实链路增加 Markdown、CSV、HTML、MHTML 和
  安全 ZIP；ZIP 最终验证解出的 Markdown 记录，而不是把归档本身伪装为已索引。
- CI 使用仅绑定 loopback 的确定性 OpenAI-compatible embedding 端点，避免真实
  模型服务、网络和凭据影响打包验收。

## 当前验收状态

| 项目                                      | 状态   |
| ----------------------------------------- | ------ |
| 现有 CLI 行为特征测试                     | 已通过 |
| MARA application service 单元/集成测试    | 已通过 |
| Sidecar 认证、参数、响应和事件契约        | 已通过 |
| Electron IPC sender、参数和原生选择器测试 | 已通过 |
| React 索引/删除状态覆盖                   | 已通过 |
| Linux 开发态真实索引/刷新/删除 smoke      | 已通过 |
| Linux 开发态轻量支持格式矩阵              | 已通过 |
| 当前代码的 Linux 自包含组合包 smoke       | 已通过 |
| 完整 `ktem` package gate                  | 已通过 |
| 完整 `slide_cli` package gate             | 已通过 |
| 当前代码的 Windows 原生组合包/Defender    | 已通过 |
| 当前代码的 Ubuntu 22.04/24.04 smoke       | 已通过 |

当前基线重新验证已取得完整 package green：`ktem` 为 1,632 passed，`slide_cli`
完整测试包也全部通过。Canonical runtime 新增的生成参数已同步到兼容 facade，并以
独立提交锁定公开请求契约和历史位置参数 ABI。

## 跨平台 CI 证据

2026-08-08 的
[Desktop Gate 3 运行 31267984102](https://github.com/262412/MARA/actions/runs/31267984102)
基于提交 `f35a9b4e0c2b9ce45776d827347ed40d1f6e6759`，三个任务全部成功：

- Windows Server 2022：原生构建、非空 Doctor/Files/Sessions、真实后台文本索引、
  Files 刷新、删除预置与新索引记录、最终空列表，以及 Defender 扫描。
- Ubuntu 22.04：原生构建并完成同一真实索引/刷新/删除 smoke。
- Ubuntu 24.04：使用 Ubuntu 22.04 的同一组合包和数据快照完成跨版本复验。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9024781798  | 395,896,042 | `eb5aaf9c28b85b424a9991c5260b8f7eb4096867fa081c6fb47728a4c940f210` |
| Windows smoke 诊断      | 9024774847  | 1,040       | `d03645c9686e4daea687815e02860bb7cc3293c2ffda39fd27081eb4c40106d6` |
| Windows Defender 诊断   | 9024775013  | 359         | `5d153c261bc917a0b05e886cbab0fee0757847d7f730f0be7dcc95b4e63b4df5` |
| Ubuntu 22.04 完整组合包 | 9024780867  | 412,444,792 | `ec4cf85d9f034e6524e44b14c3f9e434ef8a76b00380f51c78c24d382dfbaedb` |
| Ubuntu 22.04 包体测量   | 9024781056  | 1,457       | `057e35a7550fa0ca98e41c68df7f235d16a5d167b017c99beb8a29e752fd75fe` |

Artifact digest 均为 GitHub Actions 返回的 SHA-256。完整 Windows 包只有 Defender
扫描成功后才会上传；诊断证据独立使用 `always()`，扫描失败不会保存完整可执行包。

| 指标                   | Windows Server 2022                                                | Ubuntu 22.04                                                       |
| ---------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 发布目录 apparent size | 997,297,210 bytes                                                  | 1,086,008,815 bytes                                                |
| 发布目录文件数         | 2,705                                                              | 2,106                                                              |
| smoke 总耗时           | 9.044 秒                                                           | 12.22 秒                                                           |
| smoke 峰值常驻内存     | 101,060,608 bytes，约 96.4 MiB                                     | 451,636 KiB，约 441 MiB                                            |
| Sidecar SHA-256        | `3bc72162d769e600e913b63cc7a25441624792d0c57f6c2557891d735b780ab1` | `485a579c74160b53dec3e6cdcda0d42de10fe6ff157024339718bb14b8d6500b` |
| 原生依赖缺失           | 打包启动和真实索引通过                                             | `ldd` 无 `not found`                                               |

Defender 证据还确认实时防病毒与反恶意软件服务开启，移除了 runner 的 `D:\` 整盘
排除，启用了 archive scanning，并得到零检出结果。Ubuntu 24.04 没有重新构建，而是
复用 Ubuntu 22.04 的同一产物和数据快照，因此该任务提供的是发行版兼容证据。

## CLI/Desktop 数据兼容证据

2026-08-08 的
[Desktop Gate 3 运行 31268799913](https://github.com/262412/MARA/actions/runs/31268799913)
基于提交 `3796e57dfb14893735faabc38b8e83f7676d3d26`，再次取得 Windows、Ubuntu
22.04 和 Ubuntu 24.04 三任务成功：

- Ubuntu 22.04 先由正式 `MARA docqa index` 在 Desktop 数据副本中索引
  `gate3-cli-compat.txt`；CLI 随后看到预置记录和 CLI 新记录共 2 项。
- 同一打包 Desktop 读取这 2 项，再真实索引自己的文本记录，并通过现有
  `DeletionCoordinator` 删除全部记录；CLI 复查为 0 项。
- Windows 上 CLI 在启动打包应用前读取到同一 Desktop 预置记录，Desktop 删除后
  CLI 复查为 0 项。Windows CLI 写入不作为本项证据，避免绕过文件 artifact 的
  fail-closed 安全边界。
- Ubuntu 24.04 继续复用 Ubuntu 22.04 组合包和数据快照完成跨版本 smoke。

脱敏摘要位于 Linux metrics artifact `9025007551` 和 Windows smoke diagnostics
artifact `9025008201`；只保留阶段、记录数和文件名，不保留 CLI 返回的本地路径。
对应 Actions digest 分别为
`d819d0092bdf01ba13e3249f418194193002332f32d6dbb69681552e0289f8d2` 和
`8489e02f519f1ac93c70631c67667eb5cd25ace1c38b11a069b28c70b0ec6e17`。

## 轻量格式矩阵 CI 证据

2026-08-08 的
[Desktop Gate 3 运行 31269454199](https://github.com/262412/MARA/actions/runs/31269454199)
基于提交 `fce98436687886d3fc8b28587dabc095943c133b`，Windows Server 2022、Ubuntu
22.04 和 Ubuntu 24.04 三任务全部成功。打包应用在真实 DocQA runtime 中逐项要求
TXT、Markdown、CSV、HTML、MHTML 和 ZIP 解出的 Markdown 记录存在、响应不含
路径，再删除全部记录；任一格式缺失都会使进程非零退出。Ubuntu 24.04 继续复用
Ubuntu 22.04 的同一组合包和数据快照。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9025204769  | 395,898,518 | `c223d4986a6f9732ea41a992e77554e7c309022cc7c68210bed3f8884cc76725` |
| Windows smoke 诊断      | 9025199251  | 1,442       | `091c184f193082a96d94041f88da0cf9eb2694adbb2a4f95e742830b3d93e701` |
| Windows Defender 诊断   | 9025199390  | 359         | `238641bdad2bfe7ad5089ded2e3a02b6abad647ba8b100bd781ae0cd07610773` |
| Ubuntu 22.04 完整组合包 | 9025203227  | 412,481,830 | `1054f7ad4675bad8002720d40865112fff0b325455aabf9db7db9a69ab36a220` |
| Ubuntu 22.04 包体测量   | 9025203384  | 1,853       | `7f19c306ad7186d6908ffcf117c4b405a616cc66fdcb315dee5566925181df23` |

本轮 Windows smoke 用时 18.666 秒、峰值工作集 99,999,744 bytes；Ubuntu 22.04
用时 13.93 秒、最大 RSS 482,120 KiB。Windows 发布目录为 997,302,646 bytes、
2,705 个文件，Ubuntu 发布目录为 1,086,013,990 bytes、2,106 个文件；Linux
`ldd` 无缺失依赖。两平台最终 CLI/Files 复核均为 0 项。

## Linux 开发机参考测量

2026-08-08 在当前 Linux 开发机对自包含 Electron + PyInstaller 组合包执行断网
smoke。测试把外部 HTTP/HTTPS 代理指向不可达 loopback，只允许本地确定性
embedding server；真实索引、列表刷新、删除预置文件、删除新索引文件及最终空列表
均通过，日志没有下载尝试或路径泄漏。

| 指标                              | 结果                                                               |
| --------------------------------- | ------------------------------------------------------------------ |
| 组合发布目录 apparent size        | 1,067,533,566 bytes，约 1.00 GiB                                   |
| PyInstaller Sidecar apparent size | 741,030,380 bytes，约 707 MiB                                      |
| 发布目录文件数                    | 2,035                                                              |
| 真实索引/刷新/删除 smoke 总耗时   | 11.34 秒                                                           |
| smoke 峰值常驻内存                | 390,448 KiB，约 381 MiB                                            |
| swap                              | 0                                                                  |
| Sidecar 直接动态链接缺失          | 0                                                                  |
| Sidecar SHA-256                   | `a411ac4cc172800dc0aae342de1e1f56cef9b7c660d247628d562e7aaccb363a` |

打包验证实际关闭了多类只会在冻结运行时暴露的问题：动态 Chroma、TheFlow 和
tiktoken 模块，Chroma migration SQL，LlamaIndex NLTK 数据，以及 Chroma 默认
embedding function 的 ONNX/tokenizers 原生依赖。初始可运行包约 1.33 GB；排除
本切片不使用的 Numba/LLVM 加速器和 Google provider SDK 后降至约 1.00 GiB，
离线 smoke 仍通过。

Gate 3 引入的 LanceDB/Lance/PyArrow 存储链使包体和内存显著高于 Gate 2 基线，
当前记录为发布风险而不是隐藏该成本。后续只能在保持真实 DocQA 索引语义、CLI
兼容和跨平台 smoke 的前提下继续裁剪。

## 剩余验收与风险

1. 在 Windows 10/11 产品 VM 对当前 Gate 3 包执行原生选择器、重复启动、任务恢复、
   数据目录和残留进程验收。
2. 增加拖放、批量选择，以及 PDF、Office 和图片的支持格式矩阵。文本、Markdown、
   CSV、HTML、MHTML 和 ZIP 已通过 Windows/Ubuntu 原生组合包真实索引/删除。
3. 增加大文件、部分失败、运行中取消、模型不可用、磁盘满、数据库锁和 Sidecar
   强制退出的组合包故障注入。模型 503 → 脱敏失败 → 原任务重试成功已通过 Linux
   开发态真实 runtime，并已接入 Windows/Ubuntu 打包工作流，仍需取得当前提交的
   原生 CI 证据。当前取消在文件边界协作式生效，不会强杀正在执行的单文件
   parser/vector write；该边界必须在长文件验收中明确验证。
4. 当前 LlamaIndex 0.10 将 `pypdf` 限制在 4.x，无法直接采用修复
   GHSA-fp3f-mc75-235c 与 GHSA-fwg2-594c-jp42 的 6.15.0。两项恶意 PDF
   资源耗尽风险已登记为 R22；PDF 必须完成资源限制回移或 reader 升级及故障注入，
   才能进入 Verified 格式矩阵。

CLI/Desktop 同一数据副本的索引、读取和删除语义兼容已由自动化关闭；这不授权
Desktop 直接写入用户现有 `KH_APP_DATA_DIR`。旧数据空间探测、迁移、备份、回滚和
并发写入仍属于后续独立迁移切片，开发期继续只写独立 Desktop 数据根。
