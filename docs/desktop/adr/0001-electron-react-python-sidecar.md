# ADR-0001：Electron + React + Python Sidecar

- 状态：Accepted
- 日期：2026-07-30
- 决策人：MARA 产品/开发

## 背景

MARA 当前的 Web UI、CLI 和 DocQA 运行时主要由 Python 实现。新的桌面应用需要
覆盖 Windows 10/11 与 Ubuntu 22.04/24.04，并在不要求用户安装 Python 的前提下
复用既有文档处理、检索、引用、预览、图谱和 Studio 能力。同时，目标界面需要
成熟的桌面工作台布局和较高的 React 生态复用能力。

## 决策

采用一套仓库内代码，分为：

- Electron Main：桌面生命周期、原生权限、文件、凭据和进程管理。
- React Renderer：产品界面与交互。
- Python Sidecar：版本化本地 API，调用 MARA application services。
- 原生双平台流水线：分别构建 Windows x64 和 Linux x64 自包含产物。

Renderer 使用沙箱和上下文隔离，通过窄 Preload API 访问 Main。Main 启动绑定
回环随机端口的 Sidecar，并用每次启动生成的令牌认证。

## 选择理由

- 最大限度复用现有 Python 业务能力，避免重写 DocQA。
- React 适合实现三栏、流式消息、图谱、预览和复杂状态。
- Electron 对 Windows/Linux 的窗口、安装、无障碍和生态支持成熟。
- 进程隔离使 Python 崩溃、重启和日志可单独管理。
- 一套业务代码仍允许在打包、签名和平台集成层做必要差异化。

## 接受的代价

- 安装包和内存占用高于纯原生壳层。
- Electron、Node、Python 和 MARA 依赖形成多层供应链。
- Sidecar 带来端口、认证、进程退出、协议版本和流式通信复杂度。
- PyInstaller 必须在目标操作系统上构建，不能只用 Linux 产出 Windows 包。
- Windows 与 Linux 更新机制不能完全相同。

## 被否决的主要替代方案

| 方案                              | 未采用原因                                                                      |
| --------------------------------- | ------------------------------------------------------------------------------- |
| 继续只提供浏览器 Web UI           | 缺少安装、原生文件、凭据、后台任务和桌面生命周期                                |
| Electron 直接嵌入当前 Gradio 页面 | 只能“套壳”，难以得到目标信息架构、安全边界和桌面体验                            |
| 全部改写为 TypeScript             | DocQA 与文档处理重写风险和验证成本过高                                          |
| Tauri + React + Sidecar           | 包体有优势，但增加 Rust/平台 WebView 差异；当前团队和需求优先复用 Electron 生态 |
| Python GUI 框架                   | 复杂三栏 Web 交互、流式内容和现有前端资产迁移成本更高                           |

## 约束

- 不破坏 `MARA` / `MARA-cli` 和现有 Web UI。
- 不允许 Renderer 直接访问 Node、文件系统或 Sidecar 凭据。
- 不允许运行时加载远程前端代码或 CDN 资源。
- 不允许最终安装包依赖系统 Python。
- 所有 Sidecar API 必须版本化并有契约测试。
- 每个平台必须在原生 runner 构建、安装和 smoke test。

## 复审触发条件

- Gate 2 证明自包含包体或冷启动无法达到可接受范围。
- Electron 在目标系统出现无法缓解的安全或可访问性阻塞。
- 真实 MARA 服务无法从 Gradio 事件链中稳定解耦。
- 产品范围新增移动端、macOS 或强制企业商店分发。
