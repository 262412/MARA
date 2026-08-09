# MARA Desktop

这个目录包含 Gate 1 壳层、Gate 2 真实数据切片和已完成自动化的 Gate 3 子切片：

1. Electron Main 能启动、认证、检查和有序关闭 Python Sidecar。
2. React 能承载 Codex 式三栏信息架构，同时保持 MARA 的功能和术语。
3. Renderer 保持沙箱和上下文隔离，只通过窄 Preload API 获取脱敏运行状态。
4. Doctor、Files、Sessions 复用 `slide_cli.docqa_runtime` 的 application service，
   通过 FastAPI、明确 IPC 和 React 四态贯通。
5. 启动期间的数据请求等待 Sidecar healthy；OpenAPI 生成共享 TypeScript 响应
   类型并由验证脚本检查漂移。
6. 原生文件选择/拖放、后台索引、取消/重试、Files 批量删除和故障恢复复用现有
   DocQA runtime，并通过组合包 smoke。
7. 会话详情、新建任务、客户端搜索、重命名和删除通过 owner-scoped application
   service、认证 Sidecar 与明确 IPC 贯通。
8. 文档/多文档问答复用 `DocQARuntime.stream_turn()`；流式状态、停止、原范围重试、
   partial answer 和安全引用身份通过窄任务 API 与组合包 smoke 贯通。

它**不是完整 MARA Desktop**。页级/选中文本问答范围、引用跳页、预览、Notes、
Studio、Resources、Settings、Help 和迁移仍按功能矩阵逐个切片接入。当前 Sidecar
只开放版本化、按能力命名的 Doctor、Files、Sessions、会话管理、索引和问答任务
端点，不提供通用 URL 请求。

## 目录

```text
apps/desktop/
├── electron/     # Main、Preload、私有协议和 Sidecar supervisor
├── shared/       # Main、Preload 和 Renderer 共用的稳定 TypeScript 契约
├── sidecar/      # FastAPI adapter 与 MARA application service
├── src/          # React 三栏界面
├── scripts/      # PyInstaller Sidecar 构建与 Electron 打包
└── package.json  # 锁定依赖与双平台打包入口
```

## 本地验证

```bash
cd apps/desktop
npm ci
npm run contracts:check
npm run verify
npm start
```

Linux CI 可通过虚拟显示运行完整进程 smoke：

```bash
xvfb-run -a npm run smoke:electron
```

开发启动会使用 `MARA_DESKTOP_PYTHON`，未设置时 Linux 使用 `python3`、
Windows 使用 `python`。这只用于开发；发布包始终启动内置 PyInstaller 产物。

## Sidecar 打包

先在当前平台安装固定的构建依赖：

```bash
python -m pip install -r sidecar/requirements-build.txt
npm run sidecar:bundle
```

然后在对应原生系统生成可运行的自包含原型目录：

```bash
npm run package:linux
npm run package:windows
```

PyInstaller 不是跨平台编译器，因此 Linux 不能作为 Windows Sidecar 的正式构建
来源。Linux 正式产物在 Ubuntu 22.04 构建，并在 Ubuntu 22.04/24.04 验证。
Gate 1 使用 Electron Packager 验证组合后的应用目录；NSIS、`.deb` 和 AppImage
安装器属于 Gate 2 的原生 CI 工作，并按发布计划选择和锁定制作工具。
打包脚本只把 `dist`、`dist-electron` 和运行清单放进 `app.asar`，源码、测试、
开发依赖与 PyInstaller 中间产物不会重复进入发布目录。

## 已验证和未验证边界

原型应验证：

- 版本化 stdout 握手、回环随机端口和 Bearer 令牌。
- Renderer 不获得 Sidecar 端口或令牌。
- 自定义 `mara://` 资源协议阻止路径越界。
- Node integration 关闭、context isolation 和 sandbox 开启。
- Sidecar 正常退出以及父进程管道关闭后的自退出。
- 1440px 三栏和 1024px 检查器覆盖布局。

原型不声称验证：

- 全量 MARA/PyTorch/ONNX/文档依赖的包体和冷启动。
- Windows 签名、Linux 包依赖和自动更新。
- 现有数据迁移或 CLI/Desktop 并发写入。
- 完整功能对齐。

Gate 2 的本地 Linux 指标和跨平台 CI 边界记录在
[Gate 2 纵向切片证据](../../docs/desktop/gate-2-vertical-slice-evidence.md)。
Gate 3 的当前实现与剩余验收记录在
[Gate 3 文件索引纵向切片证据](../../docs/desktop/gate-3-file-indexing-evidence.md)、
[Gate 3 会话详情纵向切片证据](../../docs/desktop/gate-3-session-detail-evidence.md)和
[Gate 3 会话管理纵向切片证据](../../docs/desktop/gate-3-session-management-evidence.md)、
[Gate 3 会话新建纵向切片证据](../../docs/desktop/gate-3-session-creation-evidence.md)、
[Gate 3 真实问答纵向切片证据](../../docs/desktop/gate-3-query-streaming-evidence.md)。
其余项目由
[发布与验收计划](../../docs/desktop/release-and-acceptance-plan.md)
中的 Gate 2–5 覆盖。
