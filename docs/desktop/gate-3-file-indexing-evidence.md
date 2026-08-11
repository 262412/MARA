# MARA Desktop Gate 3 文件索引纵向切片证据

## 结论

Gate 3 的首个纵向切片是“原生文件导入 → 后台索引 → Files 刷新/删除”。实现已
贯通 React、Preload、Electron Main、认证 Sidecar 和现有 MARA DocQA runtime，
当前状态为 **In progress**。只有 Windows、Ubuntu 原生组合包均完成真实索引/删除
smoke，并补齐产品 VM、支持格式与异常场景验收后，才能升级为 `Verified`。提交
`fce9843` 已关闭 Windows Server 2022、Ubuntu 22.04/24.04 的轻量格式矩阵自动化
缺口；提交 `e0bff90` 又关闭磁盘满、数据库锁和 5 MiB 文件的 Windows/Ubuntu
原生组合包验证；提交 `894c994` 进一步关闭批量删除和安全拖放 handoff 的
Windows/Ubuntu 组合包验证；提交 `d087be1` 又关闭 DOCX、XLSX 和 PPTX 的现代
Office 直接文本索引矩阵。剩余项不再包含原生构建流水线、文本类或现代 Office
格式跨平台 smoke、批量删除、拖放 handoff 或这些故障恢复场景。

2026-08-11 的索引首次启动修复基线为
`4112e99f5f9d6beccb06f67e5e4e3e160beb3129`。当前源码已重新取得 Ubuntu 22.04
原生构建、Ubuntu 24.04 同包复验、Windows Server 2022 原生构建和 Defender
零检出证据；无 embedding 配置时会在创建任务前阻断，而不是生成必然失败的任务。
当前包仍未在 Windows 10/11 干净产品 VM 验收，因此本切片继续保持
**In progress**，不能标记为 `Verified`。

本切片不复制 Gradio callback 或 DocQA 索引/删除业务逻辑，也不修改 `MARA`、
`MARA-cli` 命令、Click 参数、Gradio 事件链、数据库 schema 或现有会话字段。

## 公共表面与安全边界

- Main 通过原生选择器取得文件路径；Renderer 只调用 `desktop.importFiles()`。拖放时
  Renderer 把 Web `File` 交给 `desktop.importDroppedFiles(files)`，Preload 用
  `webUtils.getPathForFile()` 直接解析给专用 IPC。两条路径都不向 Renderer 提供本地
  路径、选择器参数或任意文件读取能力。
- Main 通过认证 Sidecar 的 `/v1/import-capabilities` 读取当前 FileIndex 支持扩展名，
  原生选择器不再维护一份手写格式清单；空列表或畸形扩展会失败关闭。
- Preload 新增明确的 `getLatestIndexTask`、`cancelIndexTask`、
  `retryIndexTask`、`deleteFile`、`deleteFiles` 和 `onIndexTaskStatus`；没有通用
  `invoke`、`request` 或 `readFile`。
- Sidecar 新增版本化索引任务、SSE 事件、单文件和批量删除端点。批量请求只接受
  1–1,000 个唯一不透明文件 ID；所有端点继续执行
  Bearer 认证、Origin 拒绝、请求 ID、参数校验和稳定错误契约。
- 可重试写操作使用 idempotency key。Renderer 可见数据只包含任务 ID、文件名、
  计数、状态和脱敏错误，不包含导入路径或 Sidecar 端口/令牌。
- 索引任务日志保存在独立 Desktop 数据根；启动时把未完成任务标记为
  `index_interrupted`，用户可以重试失败或未完成文件。日志写入使用临时文件原子
  替换；首次写入失败会同时回滚任务和 idempotency 登记。

## 业务逻辑复用

Desktop application service 延迟创建现有 `DocQARuntime`，索引直接调用
`index_paths()`，单项和批量删除都直接调用 `delete_files()`。删除继续由现有
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
改变已有命令行为；另一个特征测试锁定 `MARA docqa delete REF... --json` 的多文件
解析、输出顺序和删除结果。

## 自动化与 smoke

- Sidecar：索引/单项与批量删除 application service、认证、参数、响应、idempotency、SSE、
  取消、部分失败重试、重启恢复和路径脱敏。
- Electron：原生选择器所有权、磁盘支持 File 的 Preload 解析、拖放路径/扩展名失败
  关闭、窄 IPC sender/参数验证、Sidecar 请求和 SSE 解析、打包 smoke 的失败退出码。
- React：loading、success、empty、failed，以及 queued、running、partial、
  success、failed、cancelled、取消、重试、可访问多选和批量删除中状态。
- OpenAPI 继续生成 checked-in TypeScript 契约，`npm run contracts:check` 检查漂移。
- 支持格式能力契约覆盖 application service、认证 Sidecar、OpenAPI、Main 原生过滤器
  和打包 smoke；真实内容矩阵仍按格式逐项验收，能力声明不等于格式已 Verified。
- `--smoke-test-gate3` 在独立数据根预置 Gate 2 非空数据，再创建一个真实文本索引
  任务；输入先通过与拖放相同的 Main 路径/扩展名校验，并记录
  `gate3_drop_handoff=validated status_success`。随后验证 Files 中出现脱敏记录，通过
  一次批量调用删除预置和新建记录，最后验证列表为空。
- `--smoke-test-gate3-formats` 在同一真实链路增加 Markdown、CSV、HTML、MHTML、
  DOCX、XLSX、PPTX 和安全 ZIP；每条记录必须有非零 tokens、明确 loader 且不含
  路径。ZIP 最终验证解出的 Markdown 记录，而不是把归档本身伪装为已索引。
- `--smoke-test-gate3-model-unavailable` 让确定性模型返回 503，要求任务以脱敏、
  可重试状态失败；解除故障后 `--smoke-test-gate3-retry` 重试原任务并清空 Files。
- `--smoke-test-gate3-cancel` 在首文件 embedding 请求处确定性暂停，确认运行中取消
  只在首文件完成后生效，再只重试第二个文件并清空 Files，避免用时序猜测制造竞态。
- `--smoke-test-gate3-partial` 先真实索引首文件，再提交“已存在文件 + 新文件”的批量
  任务，要求任务一成一败，重试只选择失败首项并以 `reindex` 恢复，最后清空 Files。
- `--smoke-test-gate3-sidecar-exit` 在真实 embedding 请求进行中只由 Main 强制终止
  Sidecar，要求 runtime 失败、监督器按指数退避自动重启、同一数据根中的任务变为
  `index_interrupted`，再重试唯一未完成文件并清空 Files；该测试控制不进入 Preload
  或 Renderer IPC。
- `--smoke-test-gate3-large-file` 生成确定性 5 MiB 文本，真实执行解析、分块、
  embedding、Files 刷新和删除；单独记录 index/delete 耗时和进程峰值内存。该
  canary 是容量回归点，不代表产品最大文件限制。
- `--smoke-test-gate3-disk-full` 在第一次任务 journal 写入处注入真实 ENOSPC，要求
  Sidecar 返回稳定、可重试的 `index_storage_full`，不保留未调度任务；同一进程
  恢复写入后重新创建任务并完成真实索引/删除。
- `--smoke-test-gate3-database-lock` 在第一次 application service 索引调用注入
  SQLite 锁，要求任务以 `index_database_locked` 脱敏失败；重试原任务后完成真实
  索引/删除。两项开关只存在于 Main 到 Sidecar 的组合包 smoke 环境，不进入 IPC。
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
| Linux 开发态模型故障与运行中取消恢复      | 已通过 |
| Linux 开发态部分失败与定向重试            | 已通过 |
| Linux 开发态 Sidecar 中断与重启恢复       | 已通过 |
| Linux 开发态 5 MiB 容量 canary            | 已通过 |
| 磁盘满/数据库锁单元与 Sidecar 契约        | 已通过 |
| Windows/Ubuntu 磁盘满与数据库锁组合包     | 已通过 |
| Windows/Ubuntu 5 MiB 容量 canary          | 已通过 |
| 批量删除 application/Sidecar/IPC/React    | 已通过 |
| Windows/Ubuntu 批量删除组合包             | 已通过 |
| 拖放 Preload/Main/IPC/React 契约          | 已通过 |
| Windows/Ubuntu 拖放 handoff 组合包        | 已通过 |
| Windows/Ubuntu 现代 Office 索引组合包     | 已通过 |
| 当前代码的 Linux 自包含组合包 smoke       | 已通过 |
| 完整 `ktem` package gate                  | 已通过 |
| 完整 `slide_cli` package gate             | 已通过 |
| 当前代码的 Windows 原生组合包/Defender    | 已通过 |
| 当前代码的 Ubuntu 22.04/24.04 smoke       | 已通过 |

当前基线重新验证已取得完整 package green：`ktem` 为 1,632 passed，`slide_cli`
完整测试包也全部通过。Canonical runtime 新增的生成参数已同步到兼容 facade，并以
独立提交锁定公开请求契约和历史位置参数 ABI。

## 索引首次启动故障修复证据

2026-08-11 的
[Desktop Gate 3 运行 31458864077](https://github.com/262412/MARA/actions/runs/31458864077)
基于提交 `4112e99f5f9d6beccb06f67e5e4e3e160beb3129`，三个任务全部成功：

- TheFlow `STORAGE` 固定为 `<DesktopDataRoot>/cache/theflow`。Ubuntu 从只读系统
  工作目录启动；Windows 工作目录 ACL 的写入探针得到拒绝。两平台都确认工作目录、
  安装目录和干净 checkout 没有创建 `.theflow`，任务进度实际位于 Desktop cache。
- Windows 先在干净 `%APPDATA%/MARA`、未创建任何 fixture 或任务且清除所有受支持
  provider 变量的条件下启动。Doctor 返回 `indexing_ready=false`、
  `embedding_not_configured`、`retryable=false`；Renderer 显示配置动作并禁用导入，
  `latest_task=empty`、`task_created=false`，且没有 `index-tasks.json` 或 progress。
- 随后才配置仅绑定 loopback 的 OpenAI-compatible provider。Windows 和 Ubuntu
  均通过真实 TXT 与轻量/现代 Office 格式索引、Files 刷新、拖放 handoff 和一次
  批量删除；Windows 记录 `import_success=true` 和 `count_10 status_success`。
- `embedding_unavailable`、`index_storage_full`、`index_database_locked` 的打包态
  故障恢复均成功；取消、部分失败、Sidecar 中断和 5 MiB canary 也保持通过。缺配置、
  缺 provider 依赖、源文件权限、401/403、503、磁盘满、数据库锁和未知异常的稳定
  code/retryable/脱敏契约另由 Sidecar 单元与响应契约测试覆盖。
- OpenAI/Azure 是 Desktop 可选默认 provider，包内真实包含 `openai`；Google 不属于
  当前 Desktop 默认支持范围，不会因占位 key 或缺失包被选择。维护日志只记录
  request/task ID、稳定类别和异常类型，并写入 `<DesktopDataRoot>/logs`。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9089193810  | 410,623,997 | `98ec06d99c6b5d69e922f4c627337aef22cdb73dedb9b1bbf11527b17024df53` |
| Windows smoke 诊断      | 9089183113  | 7,711       | `812ffbd6868b4a8abbaaf25e0ac4ba798701f375f6ae033c96a0877ddd08a656` |
| Windows Defender 诊断   | 9089183369  | 359         | `c0f8b88b4cd7ebccf0ed23b323e456481e2ddd22486f7ab953ea220ec7986863` |
| Ubuntu 22.04 完整组合包 | 9089178740  | 427,772,478 | `2471a8aff30942d98adeba38e6eb383e73be9c474ef41aa924fcbb692819e886` |
| Ubuntu 22.04 包体测量   | 9089178992  | 9,183       | `a7a0722f4965e6d0cfec129d9a994dd08a85e0a342974f3198ca9d0c0c984294` |

| 指标                   | Windows Server 2022                                                | Ubuntu 22.04                                                       |
| ---------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 发布目录 apparent size | 1,016,678,939 bytes                                                | 1,105,421,035 bytes                                                |
| 发布目录文件数         | 2,741                                                              | 2,142                                                              |
| 首段 smoke 耗时        | 17.023 秒                                                          | 15.94 秒                                                           |
| 首段峰值内存           | 96,604,160 bytes                                                   | 548,592 KiB                                                        |
| Sidecar SHA-256        | `7b03128d691844518f7ca7f67706becdbd666a22c85aa6969f78608c1562fb73` | `c267bbf5705c422d77c698fa3b41005d4316bbc45ae658b4e17e261c28934db8` |
| 工作目录               | ACL write denied                                                   | system read-only                                                   |
| Desktop 数据根         | `%APPDATA%/MARA`                                                   | Desktop-owned XDG data root                                        |
| 外部 `.theflow`        | 工作目录、安装目录、checkout 均不存在                              | 工作目录、安装目录、checkout 均不存在                              |

Defender 证据确认防病毒和反恶意软件服务开启，移除 hosted runner 的整盘排除，启用
archive scanning，并得到 `scan_result=no_detections`。完整 Windows 包仍只在扫描成功
后上传。Ubuntu 24.04 使用 artifact `9089178740` 的同一 Ubuntu 22.04 包完成复验。

本地当前产品源码也从 `/usr` 启动自包含 Linux 包完成同一真实索引/删除与无配置阻断；
仓库中既有、未由本修复创建的 `.theflow` 清单哈希在 smoke 前后均为
`7c9e3ab5fe92e0ce34661ca850dad72d187f778c5d167a1f02b0b566f823a38b`，未删除、
迁移或解释。补充本地包哈希为：Electron 可执行文件
`84e1078c8f38659f3785fec90b68ff47dcb7b5ed94e97e4e4cc6dd3290758991`、Sidecar
`31b754809feda4db698ff5a91ad0b37a37e9737e6f7f39c390ee13770b04e137`、归档
`2b32ac9eeaf15466c350a8d5171d219851e805c5dd62b94f6755da335adda6f9`。

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

## 现代 Office 索引 CI 证据

首个 canary
[运行 31279600739](https://github.com/262412/MARA/actions/runs/31279600739)
基于提交 `59cf195a046186ffb469832db2dc33ea5b5d1b1a`。Windows 与 Ubuntu 原生包均
正常构建，但首段格式 smoke 在 DOCX 处以 `partial` 失败：现有 Web/预览默认策略
要求先用 LibreOffice 或 Microsoft Word 转 PDF，而自包含 Desktop 包不携带这些
外部程序。该失败同时证明不能把开发环境里可直接读取的 Office 文件当作打包证据。

提交 `d087be17b9c1736153c1950e3e60844ba21ce1b3` 在 Desktop settings 初始化前固定
`KH_OFFICE_TO_PDF_INDEXING=false`，让 Gate 3 索引直接复用 MARA 的 DOCX、XLSX 和
PPTX 文本读取器；CLI 和 Web 的默认布局保真策略不变。随后
[Desktop Gate 3 运行 31279873378](https://github.com/262412/MARA/actions/runs/31279873378)
在 Windows Server 2022、Ubuntu 22.04 和 Ubuntu 24.04 三任务全部成功。

- 三个平台逐项看到 `gate3-format.docx`、`gate3-format.xlsx` 和
  `gate3-format.pptx`，且共同断言每条格式记录 tokens 非零、loader 非空、响应无
  本地路径；任务最终为 `success`。
- Windows 首段一次删除 10 条记录，Ubuntu 22.04 因另有 CLI 兼容记录一次删除 11
  条，Ubuntu 24.04 一次删除 10 条；最终 Files/CLI 复核为空。
- Windows 全部故障恢复 smoke 退出码为 0，Defender 得到
  `scan_result=no_detections`。成功运行的日志不再包含 `converter_failed`。
- 该证据验证可搜索文本索引，不代表 Office 布局保真预览、旧式 DOC/XLS/PPT 或
  原文件打开降级已经完成。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9028194876  | 395,909,390 | `ed694407c89d87eeac4ee164e809f7b9483e7f2ce9958b3591ee2868fbe6c0b3` |
| Windows smoke 诊断      | 9028187819  | 5,494       | `de7231eabea8c932ca650ce90d7909a5135d16e3f36bf603fa56138738c9d2c2` |
| Windows Defender 诊断   | 9028188021  | 358         | `668699518fa754e9811d49b6bb6151035c1d2e032c58836550af7a856afe0551` |
| Ubuntu 22.04 完整组合包 | 9028169829  | 412,995,354 | `5990f72aeb7017c53266e85c93bc0c849f26808f66c451ef2e89f76e6e686cc5` |
| Ubuntu 22.04 包体测量   | 9028169977  | 7,461       | `80c36f67581b517e53c08128c4b92ac6afb62e2e69b82b66027fb656347945d4` |

## 模型不可用恢复 CI 证据

2026-08-08 的
[Desktop Gate 3 运行 31270428345](https://github.com/262412/MARA/actions/runs/31270428345)
基于提交 `199f3807008fae231f0c71ce467d10203dcd549d`，三个任务全部成功。Windows
和 Ubuntu 22.04 组合包均让确定性模型返回 503，验证任务以 `index_failed`、
`retryable=true` 和脱敏文件名结束；解除故障后重试原任务成功，CLI 最终复核为
0 项。Windows 诊断明确记录 `fault_exit_code=0`、`retry_exit_code=0`，对应安全
摘要为 `gate3_fault=model_unavailable status=failed retryable=true` 和
`gate3_fault_recovery=status_success`。

Windows smoke 诊断 artifact 为 `9025483013`，Actions digest 为
`1fcbbf31501f5a3094422736e805763235649d89e3a440cf95a6b8d155eea27a`；Ubuntu
22.04 metrics artifact 为 `9025487490`，digest 为
`a21039aa06654b5b2468d213c0f0db9e86f751ee7bd68b67a7a9d7d31ef7205c`。完整
Windows 包 artifact `9025489782`、Ubuntu 包 `9025487365` 均未过期。Defender
artifact `9025483181` 确认引擎和服务开启、移除 `D:\` 整盘排除、启用 archive
scanning，并得到 `scan_result=no_detections`。

## 运行中取消恢复 CI 证据

2026-08-08 的
[Desktop Gate 3 运行 31271484535](https://github.com/262412/MARA/actions/runs/31271484535)
基于提交 `68245834200a820a53384860602391d8c4ab2dd3`，Windows Server 2022、
Ubuntu 22.04 原生包和 Ubuntu 24.04 跨版本任务全部成功。Windows 与 Ubuntu
22.04 均在首文件的真实 embedding 请求处暂停，发出取消后只让首文件完成，任务以
`index_cancelled` 结束；重试只选择第二个文件，最终两个记录均成功并被删除。

Windows 诊断记录 `cancel_exit_code=0`，标准输出为
`gate3_cancel=cancelled_at_file_boundary retry=status_success`，标准错误为 0 bytes；
Ubuntu 22.04 的 CLI 复核记录 `phase=cancellation-recovered`、`record_count=0`。
Defender 同时确认引擎与服务开启、移除 `D:\` 整盘排除、启用 archive scanning，
并得到 `scan_result=no_detections`。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9025794373  | 395,900,224 | `cf672f226723c7f0a071fb845ef38bfd3deacaaba214c2082eed6823165e7bc5` |
| Windows smoke 诊断      | 9025788548  | 2,960       | `8ca770b122ac18431f21c1c85078fd1c5a51de2ca4e93d18b58b66a1b1ecfe0a` |
| Windows Defender 诊断   | 9025788744  | 359         | `5e65dce8ff53fe8b424ad572fa67ce8624abc8b1ff33293fb948e2db99997b71` |
| Ubuntu 22.04 完整组合包 | 9025803423  | 412,480,543 | `c898f28f87a30d5818ee552c71c8b22f945a94daf182ee5e6aded0ad57e1a5e6` |
| Ubuntu 22.04 包体测量   | 9025803649  | 2,234       | `9454519b5e7d60cab77d910fefe5b3bf5b3ce0e611376994833d585d1cf2db84` |

同一 Windows 运行记录首段 smoke 用时 16.605 秒、峰值工作集 100,421,632 bytes，
发布目录 997,310,895 bytes、2,705 个文件。Ubuntu 24.04 复用 Ubuntu 22.04 的
同一组合包及取消恢复后重新生成的数据快照，提供发行版兼容复验。

## 部分失败恢复 CI 证据

2026-08-08 的
[Desktop Gate 3 运行 31272503516](https://github.com/262412/MARA/actions/runs/31272503516)
基于提交 `757a7b24d084d118a8cf7cc147351723fa6de022`，三个任务全部成功。Windows
Server 2022 和 Ubuntu 22.04 原生包先索引 `gate3-partial-already-indexed.txt`，
再批量提交该文件和一个新文件。任务以 `partial`、`success_count=1`、
`failure_count=1` 结束，失败条目只有已存在文件；重试任务只包含该失败文件并使用
`reindex` 成功恢复。安全摘要为
`gate3_partial=duplicate_1 success_1 retry=failed_only_success`，两平台随后均由
正式 `MARA docqa files --json` 复核为 `record_count=0`。

Windows 诊断记录 `partial_exit_code=0`；错误输出只包含脱敏文件名和冻结后的相对
模块栈，不包含用户文件路径。Ubuntu 22.04 的独立 partial stderr 为 0 bytes。
Defender 确认引擎与服务开启、移除 `D:\` 整盘排除、启用 archive scanning，并
得到 `scan_result=no_detections`。Ubuntu 24.04 复用 Ubuntu 22.04 的同一组合包和
部分失败恢复后重新生成的数据快照完成跨版本复验。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9026087168  | 395,899,748 | `58508918250ffa353c4f95fae3767d23ab99938ffce9d5c46a159daff513ccf0` |
| Windows smoke 诊断      | 9026081470  | 3,498       | `fcc36f201ea26430994d3d8b2815bcf5a612bbea8b4970a967fa9deccfb791d7` |
| Windows Defender 诊断   | 9026081671  | 359         | `afd59b95ba33fd82e56fd701bdecd3424bcdfa39250756161d0b1ccfad662fb2` |
| Ubuntu 22.04 完整组合包 | 9026092184  | 412,489,180 | `2b65e6ac4c3f8ac672bb4148b71cec96f6afd2fb928845cfe3b4da7a0df7d20f` |
| Ubuntu 22.04 包体测量   | 9026092438  | 3,166       | `e2563d9661d79652722616a9ef64e4e1b0d940e03b0a20bcec15f97bcf3c3312` |

同一 Windows 运行记录首段 smoke 用时 10.150 秒、峰值工作集 97,132,544 bytes，
发布目录 997,315,259 bytes、2,705 个文件。

## Sidecar 中断恢复 CI 证据

2026-08-08 的
[Desktop Gate 3 运行 31273511473](https://github.com/262412/MARA/actions/runs/31273511473)
基于提交 `ac3c4f897de85af3fc786a63192cc7523ecc25fc`，三个任务全部成功。Windows
Server 2022 和 Ubuntu 22.04 原生包在首文件 embedding 请求被确定性暂停后，由
Main 强制终止 Sidecar 子进程；runtime 进入 `failed`，监督器按
250/500/1,000 ms 退避且最多三次自动启动新的 Sidecar，持久任务日志把原任务恢复为
`status=failed`、`stage=interrupted`、`error.code=index_interrupted` 和
`retryable=true`。Main 在恢复 healthy 后重新发布最新任务，重试只包含唯一未完成
文件并成功。两平台安全摘要均为
`gate3_sidecar_exit=failed interrupted retry=status_success`，正式
`MARA docqa files --json` 最终复核 `record_count=0`。

Windows 诊断记录 `sidecar_exit_code=0`，Windows 和 Ubuntu 22.04 的独立 Sidecar
中断 stderr 均为 0 bytes。预期的客户端断连由确定性 embedding 测试服务器窄化
处理，不输出带构建路径的 BrokenPipe 栈。Defender 确认引擎与服务开启、移除
`D:\` 整盘排除、启用 archive scanning，并得到 `scan_result=no_detections`。
Ubuntu 24.04 复用 Ubuntu 22.04 的同一组合包和中断恢复后重新生成的数据快照完成
跨版本复验。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9026392438  | 395,901,619 | `4a97b97b079d47d8aed7d53d20ffd7f9b6bedef691448953cc74179b3f66c50c` |
| Windows smoke 诊断      | 9026385581  | 3,874       | `ed51ed96f19ebab52af1835df835afe780a12c6b5808731a33d37a6eefdf2d5d` |
| Windows Defender 诊断   | 9026385809  | 359         | `274b6ad7521997620725860d6966d6ff4514113230f25c7f2830d48c30a88394` |
| Ubuntu 22.04 完整组合包 | 9026385546  | 412,503,075 | `aba6fb0525d410c11eaa930746292bd118a8c86b1c2abe066bfbeb354b62d7ef` |
| Ubuntu 22.04 包体测量   | 9026385739  | 4,000       | `be627f455a4b12cb4271bbb426960a8fa3d4ea8b7b604643e4230c30d76361fe` |

同一 Windows 运行记录首段 smoke 用时 13.139 秒、峰值工作集 97,476,608 bytes，
发布目录 997,322,310 bytes、2,705 个文件。

## 存储故障与大文件跨平台证据

2026-08-08 的
[Desktop Gate 3 运行 31275825336](https://github.com/262412/MARA/actions/runs/31275825336)
基于提交 `e0bff900441f78e85c681d5b18f1a0f116e77077`，Windows Server 2022、Ubuntu
22.04 原生包和 Ubuntu 24.04 跨版本任务全部成功。

- Windows 与 Ubuntu 22.04 均在第一次任务日志写入处触发真实 `ENOSPC`，得到
  `index_storage_full`、`retryable=true`，不留下未调度任务；恢复写入后重新创建
  任务，真实索引、删除成功。
- 两平台均在第一次 application service 索引调用触发 SQLite
  `database is locked`，任务得到 `index_database_locked`、`retryable=true`；重试
  原任务后真实索引、删除成功。
- 两平台存储故障摘要分别为
  `gate3_storage_fault=disk_full status=failed retry=status_success` 和
  `gate3_storage_fault=database_locked status=failed retry=status_success`；故障 stderr
  只记录请求/任务标识、文件名、错误类型或稳定错误码，不含 Desktop 数据根。
- 两平台随后真实索引和删除 5,242,880 bytes 文本，正式 CLI 复核磁盘满、数据库锁
  和大文件三个阶段均为 `record_count=0`。Ubuntu 24.04 使用 Ubuntu 22.04 的同一
  组合包和恢复后数据快照完成跨版本复验。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9027040501  | 395,906,306 | `f6227a03b20ab699f7ba7c5c487d56e31825df4049494385b0cdd7c6e9c0b4dd` |
| Windows smoke 诊断      | 9027033347  | 5,275       | `bfd65862f1d37a613647f17e3e3efa519614e6f87d2e3ed0ac424c31d67f7061` |
| Windows Defender 诊断   | 9027033448  | 359         | `65810edeb1be2a0a37a40fa1b13a474f09ac10028acb7af555d691c5f538286c` |
| Ubuntu 22.04 完整组合包 | 9027036448  | 412,939,786 | `8009ecfe83b3da8d947cb8b18eef5770aa56aef07a741d011eaffc7a042c2a34` |
| Ubuntu 22.04 包体测量   | 9027036574  | 7,219       | `34386306ff67fcaed699be4c25d7672890f6feff354b2ea0f74d622e969c3597` |

Windows 大文件索引 31.932 秒、删除 4.140 秒，总进程 38.767 秒，峰值工作集
99,684,352 bytes；Ubuntu 22.04 索引 20.720 秒、删除 1.934 秒，总进程 25.45 秒，
最大 RSS 653,388 KiB。Windows Defender 同时确认引擎和服务开启、移除 `D:\` 整盘
排除、启用 archive scanning，并得到 `scan_result=no_detections`。

## 批量删除与安全拖放跨平台证据

2026-08-08 的
[Desktop Gate 3 运行 31278562223](https://github.com/262412/MARA/actions/runs/31278562223)
基于提交 `894c9942e8cf55d449f4410189be8f4b98d0bdaa`，Windows Server 2022、Ubuntu
22.04 原生包和 Ubuntu 24.04 跨版本任务全部成功。

- Windows 首段组合包 smoke 记录
  `gate3_drop_handoff=validated status_success` 和
  `gate3_batch_delete=count_7 status_success`；其余模型故障、取消、部分失败、
  Sidecar 中断、存储故障和大文件恢复也都通过批量删除完成清理，所有诊断退出码为
  0。Defender 结果为 `scan_result=no_detections`。
- Ubuntu 22.04 在同一真实索引链记录拖放 handoff 验证成功，并用一次请求批量删除
  8 条记录；Ubuntu 24.04 复用同一组合包和数据快照，记录 handoff 成功并一次删除
  7 条记录。
- handoff smoke 把输入送入与真实拖放相同的 Main 数量、绝对路径和动态扩展名校验，
  并验证路径不返回 Renderer；它不伪装成真实操作系统鼠标事件。Windows 10/11
  产品 VM 的物理拖放仍是人工验收项。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9027809001  | 395,907,975 | `8ac433fa887940d95e163a8211cd2a1bb9de2f8b6cc2fe975a8f384235a8e0ab` |
| Windows smoke 诊断      | 9027801984  | 5,476       | `723334e5fcfa19061b449b164da82f05575378b57a3d8e98c2260b8f6b110ba1` |
| Windows Defender 诊断   | 9027802225  | 358         | `278abea4aa6dd539d66e2f80252ac554d15706705f935ecb7f4246e5ff1ae7ae` |
| Ubuntu 22.04 完整组合包 | 9027804344  | 412,914,524 | `fb338d467055bf1941c6600f14975088b0bacddf52a6162133a5aad14ebdc336` |
| Ubuntu 22.04 包体测量   | 9027804559  | 7,464       | `335fa3545bb46cf3883dcb27266d86226d7cfa6bad8bb2b024f3a383140b1504` |

## 大文件问题发现与修复

2026-08-08 在独立 fastscratch 数据根运行 5,242,880 bytes 的确定性纯文本 canary。
真实 Electron/Sidecar/DocQA runtime 完成解析、分块、embedding 和 Files 记录；首次
运行暴露所有 Sidecar 请求共用 30 秒超时，导致大索引删除被误报为
`sidecar_unavailable`。修复后只有认证的 `DELETE /v1/files/{id}` 使用 300 秒上限，
其他请求仍保持 30 秒。完整索引、删除和 CLI 零残留复核通过，总耗时 3:18.90，
最大 RSS 643,000 KiB；删除约 140 秒，是明确的性能风险而不是隐藏成本。该场景已
接入 Windows 和 Ubuntu 22.04 原生包工作流。提交 `faf0cf5` 的运行
[31274522573](https://github.com/262412/MARA/actions/runs/31274522573) 中，Ubuntu
22.04 原生包及 Ubuntu 24.04 复验通过；Windows 在 338.183 秒后因删除超过 300 秒
上限而得到 `sidecar_unavailable`。根因是共享 `DeletionCoordinator` 对每个向量和
docstore ID 分别提交删除。提交 `14ea717` 将每个存储改为一次批量删除，并保留“批量
遇到缺失目标时逐项幂等清理”的兼容路径；上述运行已完成 Windows 原生复验，并把
删除从超过 300 秒降至 4.140 秒。

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
2. 增加 PDF、图片和旧式 Office（DOC/XLS/PPT）的支持格式矩阵。文本、Markdown、
   CSV、HTML、MHTML、DOCX、XLSX、PPTX 和 ZIP 已通过 Windows/Ubuntu 原生组合包
   真实索引/删除。批量选择/删除与安全拖放均已贯通 React、Preload、窄 IPC、认证
   Sidecar 和真实 DocQA runtime，并接入组合包 smoke 且通过 Windows Server 2022、
   Ubuntu 22.04/24.04；真实 OS 拖放仍需 Windows 10/11 产品 VM 验收。
3. 磁盘满/数据库锁 → 稳定可重试错误 → 恢复成功，以及模型 503 → 脱敏失败 → 原
   任务重试成功，均已通过 Windows/Ubuntu 原生组合包。运行中
   取消 → 文件边界停止 → 只重试剩余文件已通过 Windows/Ubuntu 原生组合包。取消
   不会强杀正在执行的单文件 parser/vector write。部分失败 → 只重试失败文件也已
   通过 Windows/Ubuntu 原生组合包。Sidecar 强制退出 → 自动重启 → 持久任务恢复
   → 重试成功也已通过 Windows/Ubuntu 原生组合包。5 MiB 大文件已通过两平台原生
   包，Windows 暴露的逐项删除瓶颈已改为批量删除并完成复验。其索引、删除耗时必须
   继续作为性能基线跟踪。
4. 当前 LlamaIndex 0.10 将 `pypdf` 限制在 4.x，无法直接采用修复
   GHSA-fp3f-mc75-235c 与 GHSA-fwg2-594c-jp42 的 6.15.0。两项恶意 PDF
   资源耗尽风险已登记为 R22；PDF 必须完成资源限制回移或 reader 升级及故障注入，
   才能进入 Verified 格式矩阵。

CLI/Desktop 同一数据副本的索引、读取和删除语义兼容已由自动化关闭；这不授权
Desktop 直接写入用户现有 `KH_APP_DATA_DIR`。旧数据空间探测、迁移、备份、回滚和
并发写入仍属于后续独立迁移切片，开发期继续只写独立 Desktop 数据根。
