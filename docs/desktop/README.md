# MARA Desktop

MARA 的 Electron + React 桌面入口通过 Python Sidecar 复用 Web/CLI 领域服务。
目标平台为 Windows 10/11 x64 与 Ubuntu 22.04/24.04 x64；当前是测试预览，
各功能和发行包的验收范围分别记录。

开发启动、共享配置目录、测试和打包命令统一维护在
[Desktop README](../../apps/desktop/README.md)。

本目录只保留长期设计与验收约束：

| 文档                                                  | 用途                                         |
| ----------------------------------------------------- | -------------------------------------------- |
| [功能矩阵](feature-parity-matrix.md)                  | 已接入能力、产品目标和剩余工作               |
| [架构](architecture.md)                               | 进程、IPC、生命周期、数据与模型配置边界      |
| [产品需求](product-requirements.md)                   | 用户流程、范围和完成定义                     |
| [界面规范](ux-design-spec.md)                         | 布局、交互、组件状态与快捷键                 |
| [技术决策](adr/0001-electron-react-python-sidecar.md) | Electron、React 与 Python Sidecar 的选择依据 |
| [安全边界](security-and-risk-register.md)             | 威胁、保护措施与放行要求                     |
| [发布与验收](release-and-acceptance-plan.md)          | 原生构建、安装、升级、签名与回滚要求         |

Desktop 保留 `MARA` / `MARA-cli`、DocQA 与 Web 的公共语义。
通过 `MARA_APP_HOME` 可以选择同一运行配置；数据迁移和多端并发写入需要各自的验证。
