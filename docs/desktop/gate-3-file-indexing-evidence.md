# MARA Desktop Gate 3 文件索引纵向切片证据

## 结论

Gate 3 的首个纵向切片是“原生文件导入 → 后台索引 → Files 刷新/删除”。实现已
贯通 React、Preload、Electron Main、认证 Sidecar 和现有 MARA DocQA runtime，
当前状态为 **In progress**。只有当前提交的 Windows、Ubuntu 原生组合包均完成
真实索引/删除 smoke，并补齐支持格式与异常场景验收后，才能升级为 `Verified`。

本切片不复制 Gradio callback 或 DocQA 索引/删除业务逻辑，也不修改 `MARA`、
`MARA-cli` 命令、Click 参数、Gradio 事件链、数据库 schema 或现有会话字段。

## 公共表面与安全边界

- Main 通过原生选择器取得文件路径；Renderer 只调用 `desktop.importFiles()`，
  不提供路径、选择器参数或任意文件读取能力。
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
本切片不使用的查询组件装入 Sidecar；`create_docqa_runtime()` 默认仍注册完整
查询能力，CLI 和 Web 路径保持原行为。

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
- `--smoke-test-gate3` 在独立数据根预置 Gate 2 非空数据，再创建一个真实文本索引
  任务，验证 Files 中出现脱敏记录，删除预置和新建记录，最后验证列表为空。
- CI 使用仅绑定 loopback 的确定性 OpenAI-compatible embedding 端点，避免真实
  模型服务、网络和凭据影响打包验收。

## 当前验收状态

| 项目                                      | 状态        |
| ----------------------------------------- | ----------- |
| 现有 CLI 行为特征测试                     | 已通过      |
| MARA application service 单元/集成测试    | 已通过      |
| Sidecar 认证、参数、响应和事件契约        | 已通过      |
| Electron IPC sender、参数和原生选择器测试 | 已通过      |
| React 索引/删除状态覆盖                   | 已通过      |
| Linux 开发态真实索引/刷新/删除 smoke      | 已通过      |
| 当前代码的 Linux 自包含组合包 smoke       | 已通过      |
| 完整 `ktem` package gate                  | 已通过      |
| 完整 `slide_cli` package gate             | 已通过      |
| 当前代码的 Windows 原生组合包/Defender    | 尚未产生 CI |
| 当前代码的 Ubuntu 22.04/24.04 smoke       | 尚未产生 CI |

当前基线重新验证已取得完整 package green：`ktem` 为 1,632 passed，`slide_cli`
完整测试包也全部通过。Canonical runtime 新增的生成参数已同步到兼容 facade，并以
独立提交锁定公开请求契约和历史位置参数 ABI。

## Linux 本地打包测量

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

1. 取得当前提交的 Windows Server 2022、Ubuntu 22.04 原生构建和 Ubuntu 24.04
   跨版本真实索引/删除 smoke，并保留 Defender 结果与产物指标。
2. 在 Windows 10/11 产品 VM 对当前 Gate 3 包执行原生选择器、重复启动、任务恢复、
   数据目录和残留进程验收。
3. 增加拖放、批量选择，以及 PDF、Office、图片、Markdown、文本、表格、HTML、
   MHTML、CSV、ZIP 的支持格式矩阵；当前确定性打包 smoke 只覆盖文本。
4. 增加大文件、部分失败、运行中取消、模型不可用、磁盘满、数据库锁和 Sidecar
   强制退出的组合包故障注入。当前取消在文件边界协作式生效，不会强杀正在执行的
   单文件 parser/vector write；该边界必须在长文件验收中明确验证。
5. 验证同一数据副本在 CLI 与 Desktop 间的索引和删除兼容性后，再考虑显式旧数据
   空间迁移；开发期继续只写独立 Desktop 数据根。
