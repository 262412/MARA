# MARA Desktop

Electron + React 工作台，通过认证的 Python Sidecar 复用 MARA DocQA 服务。
当前源码提供原生导入、后台索引、文件管理、会话新建/搜索/重命名/删除、文档与多文档
流式问答、停止/重试，以及 Resources、Settings、Help 基础页面。

页级/选中文本问答、引用跳页、原生预览、Notes、Studio、Graph、导出和完整资源管理
仍有未完成工作。范围见[功能矩阵](../../docs/desktop/feature-parity-matrix.md)。

## 开发启动

先按[根目录安装指南](../../README.zh-CN.md#安装-web-与-cli)准备 Python 3.11、
MARA 运行时、Qdrant 与模型配置。桌面开发还需要 Node.js 22.12 或更高版本和 npm。

```bash
cd apps/desktop
npm ci
npm start
```

`npm start` 构建应用并启动 Electron。解释器选择顺序是 `MARA_DESKTOP_PYTHON`、
仓库 `.venv`，最后才是系统 `python`（Windows）或 `python3`（Linux）。
发布包始终使用内置 PyInstaller 产物。

## 与 Web、CLI 共享配置和会话

给三端设置相同的绝对路径 `MARA_APP_HOME`。例如在仓库根目录选择已有配置目录：

```powershell
$env:MARA_APP_HOME = (Resolve-Path .mara/runtime).Path
```

Bash 对应 `export MARA_APP_HOME="$PWD/.mara/runtime"`。
三端读取该目录中的 `config/.env`、`config/flowsettings.py` 和已有模型记录；
`KH_APP_DATA_DIR` 指定实际数据目录，默认是 `MARA_APP_HOME/data`。
Desktop 的窗口状态、任务日志和缓存放在 `MARA_APP_HOME/desktop`。
使用相同用户与来源选择即可继续已有会话；检查 `MARA app doctor` 的实际路径。

未设置 `MARA_APP_HOME` 时，Desktop 保持独立目录：Windows 为 `%APPDATA%/MARA`，
Linux 为 `$XDG_DATA_HOME/MARA` 或 `~/.local/share/MARA`。
选择共享配置目录不会自动迁移旧数据。多端同时修改同一会话的并发行为尚未验收。

## 验证与打包

在已经准备好的开发环境中运行：

```bash
npm run contracts:check
npm run verify
```

Linux 进程 smoke 使用 `xvfb-run -a npm run smoke:electron`。
验证覆盖 Electron、Renderer、Sidecar、生成的 API 契约与构建。

在对应原生平台的独立构建环境中安装 `sidecar/requirements-build.txt`，再运行：

```bash
npm run sidecar:bundle
npm run package:windows
# Linux 构建机使用 npm run package:linux
```

PyInstaller 不能跨平台构建。源码启动、组合包 smoke、安装器、签名和干净系统验收
是不同检查；发布要求见[发布与验收计划](../../docs/desktop/release-and-acceptance-plan.md)。

## 代码边界

- `electron/`：窗口、Preload、窄 IPC、凭据和 Sidecar 生命周期。
- `shared/`：Main、Preload 与 Renderer 共享的 TypeScript 契约。
- `sidecar/`：FastAPI adapter 与 MARA application service。
- `src/`：React 页面与任务状态。
- `scripts/`：契约生成、验证、PyInstaller 与 Electron 打包。

Renderer 保持 sandbox/context isolation，通过窄 Preload API 访问服务；
Sidecar 令牌、端口和本地绝对路径不进入 Renderer。
长期设计约束见[桌面架构](../../docs/desktop/architecture.md)和
[安全边界](../../docs/desktop/security-and-risk-register.md)。
