# MARA Desktop Gate 2 纵向切片证据

## 结论

Doctor、Files、Sessions 的 Linux 端到端纵向切片已经实现并通过开发态与打包态
真实 smoke。整体 Gate 2 状态仍为 **In progress**，不能标记为 `Verified`：
Windows 原生包、Windows Defender、Ubuntu 22.04/24.04 的工作流已经建立，但
对应 runner 尚未产生本次变更的结果；非空文件和会话数据的跨平台包 smoke 也仍
需要记录。

## 公共表面与边界

本切片新增或调整：

- `apps/desktop/shared/` 中独立的 Runtime、Doctor、File、Session TypeScript 契约。
- Sidecar `GET /v1/doctor`、`GET /v1/files`、`GET /v1/sessions`。
- `desktop.getDoctor()`、`desktop.listFiles()`、`desktop.listSessions()`。
- Renderer 中 Doctor、Files、Sessions 的 loading、success、empty、failed 和
  retry 状态。
- `MARA_DESKTOP_DATA_DIR` 下的独立 Desktop config/data/cache 路由。

本切片没有修改 `MARA` / `MARA-cli` 命令、Click 参数、Gradio 事件链、数据库
schema 或现有会话字段。Sidecar 直接复用：

- `collect_docqa_doctor_payload()`
- `collect_docqa_file_records()`
- `collect_docqa_session_summaries()`

Files API 只投影稳定元数据，不把服务返回的本地 `path` 暴露给 Renderer。

## 契约与安全证据

- FastAPI 负责 OpenAPI、响应模型与参数验证。
- 每个请求携带或生成 `request_id`；错误固定为 `code`、`message`、`details`、
  `retryable`、`request_id`。
- 缺少或错误 Bearer 令牌返回 401；带浏览器 `Origin` 的请求返回 403。
- 三个 v1 查询端点拒绝未声明参数。
- Main 保存随机端口和令牌；Preload 不向 Renderer 暴露任一字段。
- IPC 逐方法注册并校验 `mara://app/` sender；三个读取方法不接受参数。
- Desktop 启动时覆盖旧的 `KH_APP_DATA_DIR`，并强制使用包内 runtime settings。
  config、data、cache 和兼容 `ktem_app_data` 都位于 Desktop 数据根。

## 测试结果

2026-07-30 在当前 Linux 开发机执行：

| 层                    | 结果                                                     |
| --------------------- | -------------------------------------------------------- |
| Electron/IPC          | 9 passed                                                 |
| React 状态渲染        | 3 passed；覆盖 Files、Sessions、Doctor 的四态与重试入口  |
| Sidecar/application   | 9 passed；覆盖认证、Origin、参数、响应、错误和 OpenAPI   |
| Runtime 路径          | 1 passed；Desktop config/data/cache 全部约束在独立数据根 |
| Desktop 综合验证      | `npm run verify` 通过                                    |
| `slide_cli` 回归门    | 完整 package test 通过                                   |
| `ktem` 回归门         | 1,529 passed                                             |
| 开发态 Electron smoke | 真实 Doctor → Files → Sessions 顺序通过                  |
| PyInstaller smoke     | 三个真实 v1 端点顺序通过                                 |
| 非空打包数据 smoke    | 1 个文件、1 个会话；Doctor `ok=true`；本地路径未返回     |
| 组合发布目录 smoke    | `MARA --smoke-test` 退出码 0                             |
| 代码卫生              | Python changed-files ratchet 通过；baseline 未刷新       |

新数据目录中的 Doctor 返回 `ok=false` 和
`No default FileIndex is available.`，Files/Sessions 返回空数组。这是独立新库的
正确业务诊断和空状态，不是 API 或打包失败。

## Linux 本地测量

当前开发机为 Linux 5.14、glibc 2.34；这些数据是本地基线，不代替 Ubuntu
22.04/24.04 验收。

| 指标                              | 结果                    |
| --------------------------------- | ----------------------- |
| 组合发布目录 apparent size        | 667 MB                  |
| PyInstaller Sidecar apparent size | 356 MB                  |
| Electron 主可执行文件             | 210 MB                  |
| `app.asar`                        | 264 KB                  |
| 发布目录文件数                    | 1,733                   |
| 冷启动至非空三接口 smoke 完成     | 4.89 秒                 |
| smoke 峰值常驻内存                | 145,648 KiB，约 142 MiB |
| swap                              | 0                       |
| Sidecar 直接动态链接缺失          | 0                       |
| Sidecar SHA-256                   | `291b3e0a...6c2da2b3`   |

当前包体显示 R01 仍需优化：第一切片已经排除实测不会加载的训练、推理、Gradio 和
开发工具模块，但 `slide_cli` 包初始化仍带入 PPTX、Pillow、NumPy 等依赖。后续
只能在保持 CLI 行为和特征测试的前提下，评估更轻的 application-service 包边界。

## 打包问题与修正

1. 初次 PyInstaller 构建没有跟随 workspace editable finder，打包后真实请求报
   `ModuleNotFoundError: slide_cli`。构建脚本现已显式加入三个 workspace package
   root 和 `slide_cli.docqa_runtime`。
2. 从仓库目录启动打包 Sidecar 时，runtime bootstrap 会发现仓库
   `flowsettings.py`，破坏独立 Desktop 数据边界。现在
   `MARA_DESKTOP_DATA_DIR` 会固定 config/data/cache 路径，Sidecar 强制选择
   `ktem.default_flowsettings`。
3. PyInstaller 对 `docqa_runtime.py` 做静态分析时会收集实际未由本切片加载的
   Torch、Transformers、Scipy、Pandas 等模块。构建脚本按真实运行 import
   清单排除这些模块；打包后二进制的三个真实端点已验证。
4. 开发环境一度存在 stale editable：`ktem`/`kotaemon` 指向另一个 validation
   checkout。使用当前锁文件重新同步 workspace 后，三个包都指向本仓库。

## 跨平台验收入口

`.github/workflows/desktop-gate2.yaml` 提供：

- Ubuntu 22.04 原生 Sidecar/Electron 打包、真实 smoke、包体/文件数/冷启动/
  内存和 `ldd` 证据。
- 将 Ubuntu 22.04 产物带到 Ubuntu 24.04 再运行真实 smoke。
- Windows 原生打包、真实 smoke、包体/冷启动/内存记录和 Windows Defender
  自定义扫描。

只有上述工作流实际通过，并补充 Windows 10/11 干净 VM 与非空数据记录后，
功能矩阵中的三个切片才能从 `In progress` 更新为 `Verified`。
