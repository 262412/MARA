# MARA Desktop 技术原型

这个目录是正式开发前的 Gate 1 原型，用来证明三件事：

1. Electron Main 能启动、认证、检查和有序关闭 Python Sidecar。
2. React 能承载 Codex 式三栏信息架构，同时保持 MARA 的功能和术语。
3. Renderer 保持沙箱和上下文隔离，只通过窄 Preload API 获取脱敏运行状态。

它**不是完整 MARA Desktop**。Sidecar 目前只实现 `/health`、
`/capabilities` 和 `/shutdown`，不调用真实 DocQA；界面数据也是用于设计评审的
固定场景。下一阶段必须用真实的文件、会话和 doctor 服务切片完成 Gate 2。

## 目录

```text
apps/desktop/
├── electron/     # Main、Preload、私有协议和 Sidecar supervisor
├── sidecar/      # 零第三方运行依赖的 Python 进程原型
├── src/          # React 三栏界面
├── scripts/      # PyInstaller Sidecar 构建与 Electron 打包
└── package.json  # 锁定依赖与双平台打包入口
```

## 本地验证

```bash
cd apps/desktop
npm ci
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

这些项目由
[发布与验收计划](../../docs/desktop/release-and-acceptance-plan.md)
中的 Gate 2–5 覆盖。
