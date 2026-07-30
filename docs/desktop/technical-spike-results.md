# MARA Desktop Gate 1 技术原型结果

日期：2026-07-30
结论：**轻量架构链路可行，可以进入 Gate 2；Windows 原生验证尚未执行。**

## 1. 本次证明的范围

本原型只验证 Electron + React + Python Sidecar 的桌面边界，不包含真实 MARA
DocQA 依赖。Sidecar 使用 Python 标准库提供健康、能力和关闭接口，目的是尽早发现
进程、认证、打包和 UI 架构问题，而不是用一个假后端声称功能对齐。

## 2. 环境与版本

| 项目        | 实测值                   |
| ----------- | ------------------------ |
| 开发主机    | Linux x86_64，glibc 2.34 |
| Node.js     | 24.17.0                  |
| Electron    | 43.2.0                   |
| React       | 19.2.8                   |
| Vite        | 8.1.5                    |
| TypeScript  | 7.0.2                    |
| Python      | 3.10.20                  |
| PyInstaller | 6.21.0                   |

依赖版本来自 2026-07-30 的 registry 查询并锁入
`apps/desktop/package-lock.json`。正式开发使用自动依赖更新 PR 和安全审查，不以
“永远固定当前最新版”作为维护策略。

## 3. 实测结果

| 验证项                  | 结果     | 证据摘要                                                       |
| ----------------------- | -------- | -------------------------------------------------------------- |
| TypeScript              | 通过     | Renderer 和 Electron 两套配置严格类型检查                      |
| Electron 契约测试       | 5/5 通过 | 私有资源路径、目录穿越、握手格式和协议拒绝                     |
| Sidecar 契约测试        | 3/3 通过 | 无令牌 401、健康元数据、显式能力                               |
| npm 依赖审计            | 通过     | 0 known vulnerabilities                                        |
| Renderer 生产构建       | 通过     | JS 204.14 KiB（gzip 64.84）；CSS 13.45 KiB（gzip 3.60）        |
| Electron 进程 smoke     | 通过     | 实际启动 Python，GET `/health`，POST `/shutdown`               |
| 浏览器视觉检查          | 通过     | 1440×900 三栏；1024×720 覆盖式检查器                           |
| 浏览器控制台            | 通过     | 最终 0 error / 0 warning                                       |
| 1024 布局边界           | 通过     | viewport、shell、sidebar、workspace 高度均为 720；无页面级溢出 |
| 深色主题对比度          | 通过     | 主文本 14.67:1；辅助文本 6.56:1                                |
| Linux PyInstaller       | 通过     | `onedir` Sidecar 20 MiB                                        |
| Linux Electron Packager | 通过     | 自包含原型目录 261 MiB；`app.asar` 232 KiB                     |
| 发布内容边界            | 通过     | `app.asar` 无源码、测试、开发依赖和 Sidecar 中间产物           |
| 打包后 smoke            | 通过     | 内置 Sidecar 健康/关闭成功；无残留进程                         |
| Windows 打包/安装       | 未执行   | 必须在 Windows x64 runner 原生构建                             |
| Ubuntu 22.04/24.04 安装 | 未执行   | 当前只完成 Linux 构建主机 smoke                                |

## 4. 原型过程中发现并处理的问题

1. **构建工具供应链**：最初评估的 `electron-builder` 当前依赖链报告 16 个
   high。原型改用更窄的 Electron Packager，审计降为 0。NSIS/`.deb`/AppImage
   制作工具在 Gate 2 通过原生 CI 单独选择和锁定。
2. **TypeScript 7 迁移要求**：补充 Vite CSS 类型声明，并使用已支持的
   `Node16` module resolution。
3. **1024px 高度裁切**：真实渲染发现 Grid 最小内容高度把 Composer 和侧栏底部
   推出视口。增加 `minmax(0,1fr)` 与 `min-height:0` 后复测通过。
4. **覆盖检查器可关闭性**：1024px 时原工具栏会被覆盖，已在检查器内加入明确关闭
   按钮。
5. **Sidecar 退出竞争**：首次完整 smoke 在解释器关闭时发现 stdin 缓冲锁竞争。
   改用低层 `os.read` 监视父进程管道后，重复 smoke 干净退出。

这些问题说明 Gate 1 不能只做静态文档或构建检查；真实进程和视觉自动化是后续
Gate 的固定门槛。

## 5. Gate 2 必须回答的问题

- 把真实 Files、Sessions、Doctor application service 打进 Sidecar 后，包体、冷启动
  和内存增长多少。
- PyTorch、ONNX、向量库、解析器和 Office 预览依赖在 Windows/Linux 上有哪些
  hidden import、DLL/SO 和许可证问题。
- Windows Defender、Windows 代码签名以及 Ubuntu 22.04/24.04 ABI 是否通过。
- 现有 `KH_APP_DATA_DIR` 只读探测、备份、迁移和 CLI/Desktop 双向读取是否可靠。
- SSE 长任务、取消、崩溃恢复和关闭等待策略是否满足产品需求。

在这些问题有实测答案之前，不冻结最终安装器体积和冷启动绝对预算。
