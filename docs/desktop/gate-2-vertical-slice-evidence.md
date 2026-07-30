# MARA Desktop Gate 2 纵向切片证据

## 结论

Doctor、Files、Sessions 的端到端纵向切片已经实现。提交
`e04514110277b9147e02b01ec241e955ceaa803b` 的 Windows Server 2022、
Ubuntu 22.04 原生打包，以及 Ubuntu 24.04 跨版本非空 smoke 均已通过；
Windows Defender 实际扫描也已通过。整体 Gate 2 状态仍为 **In progress**，
不能标记为 `Verified`：还需要 Windows 10 和 Windows 11 干净虚拟机上的产品
验收。

## 当前自动化证据

| 证据                 | 结果                                                                                                       |
| -------------------- | ---------------------------------------------------------------------------------------------------------- |
| Desktop Gate 2       | [run 30562505330](https://github.com/262412/MARA/actions/runs/30562505330)，3 个任务全部成功               |
| Windows Server 2022  | 原生 Sidecar/Electron 打包、非空 smoke、Defender 扫描成功；artifact `8767573657`，压缩后 254,315,311 bytes |
| Defender diagnostics | 独立 artifact `8767561828`，完整包只在扫描成功后上传                                                       |
| Ubuntu 22.04         | 原生 Sidecar/Electron 打包和非空 smoke 成功；artifact `8767567918`，压缩后 260,981,383 bytes               |
| Ubuntu 24.04         | 使用 Ubuntu 22.04 产物和同一非空数据快照完成跨版本 smoke                                                   |
| Quality gates        | [run 30562506257](https://github.com/262412/MARA/actions/runs/30562506257)，20 个任务全部成功              |

Windows Server 2022 runner 是自动化构建证据，不等同于 Windows 10/11 干净
虚拟机验收。

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

- FastAPI 负责 OpenAPI、响应模型与参数验证。Doctor、File、Session 和 Sidecar
  error 类型由 `sidecar.generate_contracts` 从当前 OpenAPI 确定性生成到
  `shared/api-contracts.generated.ts`；`npm run contracts:check` 在生成结果漂移时
  失败，并已纳入 `npm run verify`。
- 每个请求携带或生成 `request_id`；错误固定为 `code`、`message`、`details`、
  `retryable`、`request_id`。
- 缺少或错误 Bearer 令牌返回 401；带浏览器 `Origin` 的请求返回 403。
- 三个 v1 查询端点拒绝未声明参数。
- Main 保存随机端口和令牌；Preload 不向 Renderer 暴露任一字段。
- IPC 逐方法注册并校验 `mara://app/` sender；三个读取方法不接受参数。
- Desktop 启动时覆盖旧的 `KH_APP_DATA_DIR`，并强制使用包内 runtime settings。
  config、data、cache 和兼容 `ktem_app_data` 都位于 Desktop 数据根。
- Main 在创建窗口前取得唯一的 Sidecar startup Promise；启动期间发起的 Doctor、
  Files、Sessions 请求等待该 Promise，而不是提前返回 `sidecar_not_ready`。
  打包 smoke 也改为在 startup 未完成时并发发起三个数据请求。

## Gate 2 审查 P1 收口

2026-07-30 的 Gate 2 审查识别出三项阻塞问题。本轮处理结果：

1. 首次启动竞态：增加延迟启动回归测试，数据请求会等待 healthy，打包 smoke
   不再先等 ready 后才请求。
2. 供应链策略：Ubuntu 22.04 仅允许
   `desktop-gate2.yaml/package-linux-22`；Windows 仅允许
   `desktop-gate2.yaml/package-windows` 且固定为 `windows-2022`。其余任务仍
   必须使用 `ubuntu-24.04`。
3. `actions/setup-node` 的 `v4.4.0` 标签经 git tag ref 和 GitHub ref API 独立
   核对均解析到
   `49933ea5288caeca8642d1e84afbd3f7d6820020`，并登记到供应链 allowlist。
4. Desktop workflow 为 `main`/`Dev` 增加带 Desktop 路径过滤的 `push` 触发。
5. OpenAPI → TypeScript 生成与 checked-in 漂移检查已进入 Desktop verify。
6. Linux job-level XDG 路径使用 runner 本地 `/tmp/mara-desktop`；不在 job
   dispatch 前引用尚不可用的 `runner` expression context。
7. uv `0.11.19` 下载校验和按 runner 平台登记：Linux x64 为
   `70356081...947c368`，Windows x64 为 `1665fc8e...b28d61`，均来自官方 release
   的对应资产校验文件。
8. Windows PyInstaller 不再探测 Gate 2 运行路径未使用的可选 `python-magic`
   模块；排除清单独立为可测试配置，并增加回归断言，避免原生打包子进程因
   `libmagic` 导入而崩溃。
9. Ubuntu 24.04 对 Electron SUID sandbox 的所有者与权限要求比打包 runner
   更严格；跨版本 smoke 在解包后显式恢复 `root:root` 和 `4755`，未使用
   `--no-sandbox` 降级安全边界。
10. GitHub Windows runner 默认把 `C:\`、`D:\` 整盘加入 Defender 排除项。
    Defender 步骤现在解析包的绝对路径、仅移除所在盘根排除、确认引擎状态并
    启用 archive scanning；扫描无法启动或发现威胁都会失败并上传诊断证据。
11. Windows 完整包只在前置步骤全部成功（包括 Defender 扫描）时上传；
    Defender 诊断文本独立使用 `always()` 上传，扫描失败不会保存未经放行的
    完整包 artifact。
12. 双平台打包 smoke 在独立数据根中通过现有 application schema 确定性预置
    1 个 File 和 1 个 Session，再验证 Doctor `ok`、精确记录数、固定记录 ID
    以及 File 响应不包含本地路径。Ubuntu 22.04 产物携带同一数据快照供
    Ubuntu 24.04 跨版本复验。

这些修正关闭代码和策略层阻塞，但不替代 Windows 10/11 干净虚拟机验收。

## 测试结果

2026-07-30 在当前 Linux 开发机执行：

| 层                    | 结果                                                     |
| --------------------- | -------------------------------------------------------- |
| Electron/IPC          | 13 passed；包含启动等待和非空 smoke 响应契约             |
| React 状态渲染        | 3 passed；覆盖 Files、Sessions、Doctor 的四态与重试入口  |
| Sidecar/application   | 11 passed；包含契约漂移和真实非空 fixture 读取           |
| 供应链策略            | 36 passed；含非空 smoke 与 Defender artifact 隔离        |
| Sidecar 打包配置      | 1 passed；Windows 不导入未使用的 `python-magic`          |
| Runtime 路径          | 1 passed；Desktop config/data/cache 全部约束在独立数据根 |
| Desktop 综合验证      | `npm run verify` 通过                                    |
| `slide_cli` 回归门    | 完整 package test 通过                                   |
| `ktem` 回归门         | 1,529 passed                                             |
| 开发态 Electron smoke | 真实 Doctor → Files → Sessions 顺序通过                  |
| PyInstaller smoke     | 三个真实 v1 端点顺序通过                                 |
| 非空打包数据 smoke    | 1 个文件、1 个会话；Doctor `ok=true`；本地路径未返回     |
| 组合发布目录 smoke    | `MARA --smoke-test-nonempty` 退出码 0                    |
| 代码卫生              | Python changed-files ratchet 通过；baseline 未刷新       |

空数据状态仍由 React 和 Sidecar 契约测试覆盖。打包验收使用隔离的确定性数据
快照，避免只证明“空库可启动”而没有证明真实 File/Session 读取。

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
| 冷启动至非空三接口 smoke 完成     | 4.95 秒                 |
| smoke 峰值常驻内存                | 147,232 KiB，约 144 MiB |
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
- Windows 和 Ubuntu smoke 都预置一个真实 File 与 Session，并以
  `--smoke-test-nonempty` 验证三个 API 的非空响应。
- Defender 诊断证据始终上传；完整 Windows 包仅在扫描成功后上传。
- PR 以及 `main`/`Dev` 直接 push 的 Desktop 路径过滤触发。

确定性非空 smoke 的本地和双平台 CI 回归均已通过。在 Windows 10/11 干净 VM
验收完成前，功能矩阵中的三个切片都保持 `In progress`。
