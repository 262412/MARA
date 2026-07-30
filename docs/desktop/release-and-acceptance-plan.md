# MARA Desktop 发布与验收计划

## 1. 产物

| 平台                   | 主要产物                  | 辅助产物                        |
| ---------------------- | ------------------------- | ------------------------------- |
| Windows 10/11 x64      | 签名 NSIS/Squirrel 安装器 | 解压版仅用于诊断；SHA-256；SBOM |
| Ubuntu 22.04/24.04 x64 | `.deb`                    | AppImage；SHA-256；SBOM         |

首版不承诺 Snap、Microsoft Store 或企业软件中心。若以后增加，必须单独评估
沙箱、数据目录、自动更新和签名要求。

## 2. 原生构建矩阵

| Job               | Runner/基线                | 内容                                                |
| ----------------- | -------------------------- | --------------------------------------------------- |
| renderer-contract | Ubuntu                     | TypeScript、React、IPC 类型、前端单测、离线资源检查 |
| sidecar-contract  | Ubuntu + Windows           | Python 单测、API schema、握手与认证                 |
| package-windows   | Windows Server runner, x64 | PyInstaller Sidecar + Electron 安装器 + 签名        |
| package-linux     | Ubuntu 22.04, x64          | PyInstaller Sidecar + `.deb` + AppImage             |
| install-win10     | 干净 Windows 10 VM         | 安装、启动、更新、卸载                              |
| install-win11     | 干净 Windows 11 VM         | 安装、启动、更新、卸载                              |
| install-ubuntu22  | 干净 Ubuntu 22.04 VM       | `.deb`/AppImage、依赖、文件权限                     |
| install-ubuntu24  | 干净 Ubuntu 24.04 VM       | `.deb`/AppImage、Wayland/X11 smoke                  |

Python 固定同一 minor 版本和锁文件，但 Sidecar 必须在目标操作系统原生构建。
Linux 二进制在 Ubuntu 22.04 构建以维持最低 glibc 基线。

## 3. 测试金字塔

### 每个合并请求

- Python application service 与 Sidecar API 单元/契约测试。
- Electron Main 的路径、IPC sender、协议和生命周期测试。
- React 组件、状态机和键盘交互测试。
- API Schema 生成与 TypeScript 类型漂移检查。
- 现有 MARA 相关测试与代码卫生门；不得刷新卫生 baseline 来规避失败。
- 至少 Windows/Linux build smoke，不要求每次生成公开签名包。

### 每日或候选版本

- 两平台自包含打包。
- 安装、首启、重复启动、卸载、覆盖安装。
- 支持格式导入/预览矩阵。
- 模型端点、断网、代理和无凭据场景。
- Sidecar 崩溃、强制关机、休眠恢复、磁盘满和数据库锁故障注入。
- 旧数据迁移、回滚和 CLI/Desktop 兼容。
- Playwright/Electron 关键路径视觉和可访问性回归。

### 发布前人工验收

- Windows 100%、125%、150%、200% 缩放。
- Ubuntu X11/Wayland、浅色/深色主题。
- 键盘完成“导入 → 提问 → 点击引用 → 导出”。
- 屏幕阅读器 smoke：Windows Narrator、Ubuntu Orca。
- 中文/英文长文件名、空格、Unicode、深路径和只读目录。
- Windows Defender 和常见企业代理环境。

## 4. P0 关键路径

每条路径都必须记录版本、系统、输入、预期、截图/日志和结果：

1. 干净安装 → 首次设置 → doctor 通过。
2. 导入 PDF → 索引完成 → 文档级提问 → 引用跳页。
3. 导入 Office/图片/表格 → 预览或明确降级。
4. 多文档选择 → 问答 → 同名文件引用身份正确。
5. 保存答案为笔记 → 生成 Studio 产物 → 原生“保存为”导出。
6. 构建知识图谱 → 选中节点 → 节点上下文追问。
7. 生成中停止 → 保留 partial → 重试成功。
8. Sidecar 强制退出 → UI 不崩 → 重启并恢复。
9. 关闭应用 → 重新打开 → 历史、布局、来源和状态恢复。
10. 从旧数据副本迁移 → 校验 → 回滚 → 原数据不变。

## 5. 性能与容量基线

Gate 2 先测量再冻结绝对预算，避免在未知的 ML/文档依赖体积上给出虚假指标。
必须采集：

- 安装器、解包目录、首次运行缓存和一次典型索引后的磁盘占用。
- 冷/热启动到壳层、Sidecar healthy 和首个可交互任务的时间。
- 空闲、PDF 预览、索引、流式问答的内存和 CPU。
- 1、100、1,000 个文档和 1、100、1,000 个会话下的列表/搜索延迟。

冻结后采用“绝对预算 + 相对回归”双门：候选版本不得超过批准绝对值，且相对
上一个稳定版恶化超过 10% 必须解释并批准。

## 6. 更新与回滚

- Windows 使用签名更新元数据；下载后校验，失败保留当前版本。
- Electron 内置 updater 不支持 Linux，因此 Linux 首版通过 `.deb` 仓库或明确的
  新版本下载提示更新；不得承诺与 Windows 相同的静默更新体验。
- 应用二进制更新与数据 schema 迁移分离。schema 升级前备份，回滚应用时检测
  schema 兼容性。
- 公开发布保留至少一个上一稳定版安装器和对应迁移工具。

## 7. 发布清单

- [ ] 版本、协议版本、数据 schema 和发布说明一致。
- [ ] Windows/Linux 原生构建和四个系统安装矩阵通过。
- [ ] P0 功能矩阵全部为 Verified。
- [ ] 现有 `MARA` / `MARA-cli` / Web UI 回归通过。
- [ ] Windows 签名有效；Linux checksum 可验证。
- [ ] SBOM、许可证和漏洞报告已审查。
- [ ] 断网、迁移、崩溃恢复、磁盘满和更新回滚演练通过。
- [ ] 帮助、隐私说明、数据位置和卸载保留规则与版本一致。
- [ ] 已知问题有影响、规避方式和修复计划。
