# MARA Desktop Gate 3 会话详情纵向切片证据

## 结论

Gate 3 的会话详情读取已贯通 React、Preload、Electron Main、认证 Sidecar 和现有
MARA DocQA runtime。最终提交 `9c52c31962724282bbe30dd7e349758836b6926d`
在 Windows Server 2022、Ubuntu 22.04 和 Ubuntu 24.04 组合包中全部通过。

本切片状态仍为 **In progress**：自动化已经完成，但当前组合包尚未在 Windows
10/11 产品 VM 上重新执行验收。该状态只适用于“从最近任务打开并读取真实会话”，
不代表会话新建、重命名、删除、固定、搜索、来源恢复或流式问答已经完成，更不代表
整个 Gate 3 已完成。

## 公共表面与安全边界

- Sidecar 新增认证后的 `GET /v1/sessions/{conversation_id}`。会话 ID 只接受
  1–128 个字母、数字、点、下划线或连字符；认证、Origin 拒绝、请求 ID 和稳定错误
  契约与其他 Desktop API 一致。
- application service 直接调用现有 `DocQARuntime.load_session()`，继续使用已有的
  owner/public 授权语义，不调用 Click 命令，不复制 Gradio callback 或会话查询。
- 响应只投影会话 ID、名称、用户/助手文本、来源 ID、origin、公开标记和时间。
  `data_source`、用户 ID、settings、检索状态和本地路径均不进入 Sidecar 响应或
  Renderer。
- Preload 只新增 `desktop.getSession(sessionId)`；Main 同时校验 sender 和不透明
  ID。没有增加通用 `invoke`、任意 URL 请求或任意文件读取能力，Renderer 仍不知道
  Sidecar 端口和令牌。
- React 仅在用户选择左侧 Session 后读取详情，并使用请求代数丢弃快速切换产生的
  过期响应。工作区覆盖未选择、loading、success、empty、failed 和重试状态。
- 本只读切片继续关闭 reasoning、模型调用和文件 artifact。共享 DocQA 设置、列表
  读取和 runtime 初始化使用同一 service 锁，避免并发首启时覆盖能力裁剪。

## 业务逻辑复用与现有行为保护

现有 Web/CLI 会话授权特征测试
`libs/ktem/ktem_tests/test_docqa_runtime_session_authorization.py` 共 14 项通过，锁定
owner、public 和跨用户写入边界。Desktop 没有修改 `MARA` / `MARA-cli` 命令、
Click 参数、Gradio 事件链、Conversation schema 或已有会话字段。

打包 fixture 使用与现有 `Conversation.data_source["messages"]` 相同的 turn 存储
形状。Desktop 读取后只把每个 turn 展开成 `user` / `assistant` 消息，不改变底层
持久化格式。

## 自动化与本地验证

| 层级                            | 结果                                                                 |
| ------------------------------- | -------------------------------------------------------------------- |
| Web/CLI 会话授权特征测试        | 14 passed                                                            |
| OpenAPI → TypeScript 漂移检查   | 通过                                                                 |
| Electron Main/Preload           | 40 passed；窄 IPC、sender、参数和 Sidecar 响应                       |
| React                           | 8 passed；会话详情覆盖未选、loading、success、empty、failed 和 retry |
| Sidecar/application service     | 41 passed；认证、校验、404、投影和并发初始化                         |
| 打包配置                        | 3 passed                                                             |
| TypeScript 与生产 Renderer 构建 | 通过                                                                 |
| 开发态非空数据 Electron smoke   | 连续 5 次通过                                                        |
| 并发 runtime 初始化回归         | 连续 20 次通过                                                       |
| 代码卫生、格式化、目标 mypy     | 通过；未刷新卫生 baseline                                            |

每个非空组合包 smoke 都调用 `getSession(GATE2_SMOKE_SESSION_ID)`，要求固定会话 ID、
两条展开后的用户/助手消息和正确角色，并断言响应没有 `data_source` 或 `user_id`。任一
条件不满足都会让应用以非零状态退出；空数据 smoke 不伪造会话详情请求。

## 首次打包失败与修复

[运行 31281790782](https://github.com/262412/MARA/actions/runs/31281790782)
基于初始提交 `78c5d3ce189c8a78a43522fd0910954cd5fcb4cd`。Windows 和 Ubuntu
原生包都正常构建，首段索引/格式 smoke 也完成，但后续进程在并行读取 Doctor、
Files、Sessions 和 Session detail 时失败。冻结 Sidecar 的全局 runtime settings
被另一个读取线程恢复成完整 reasoning 列表，随后尝试导入本切片明确未打包的
`ktem.reasoning.simple`，最终返回 `application_service_unavailable`。

同一提交的
[Quality gates 31281790875](https://github.com/262412/MARA/actions/runs/31281790875)
还发现两个旧测试替身没有实现新增的 `get_session` protocol 方法。提交 `ea4ab46`
补齐测试替身；提交 `9c52c31` 进一步让共享 DocQA collectors 和 runtime 初始化在同一
锁内执行，并加入确定性并发回归。修复没有通过增加 reasoning hidden import 掩盖
问题，也没有扩大 Sidecar 能力或刷新卫生 baseline。

## 跨平台 CI 证据

2026-08-08 的
[Desktop 运行 31282232639](https://github.com/262412/MARA/actions/runs/31282232639)
基于提交 `9c52c31962724282bbe30dd7e349758836b6926d`，三个任务全部成功：

- Windows Server 2022 原生构建完成；非空会话详情、全部 Gate 3 索引/恢复 smoke
  退出码均为 0，Defender 为 `scan_result=no_detections`。
- Ubuntu 22.04 原生构建完成；同一非空会话详情和 Gate 3 smoke 退出码为 0，Sidecar
  `ldd` 没有 `not found`。
- Ubuntu 24.04 下载 Ubuntu 22.04 的同一组合包和数据快照，重新执行非空会话详情与
  Gate 3 smoke 并通过，没有在较新系统上重新构建来掩盖 glibc 基线。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9028836199  | 395,910,276 | `ba0827984ee4324b47dbee49bdd774ad44f5bd0c7f88467ffd3c8f4de0afea9f` |
| Windows smoke 诊断      | 9028829357  | 5,486       | `14fd09f2b0fa6fbeab50157104d94490110221828e29c3c99e713485c10b4f38` |
| Windows Defender 诊断   | 9028829574  | 358         | `0ebbfc208d73c983d42c89ea5830828c80f6dc509ab0cd073821929bc5366c74` |
| Ubuntu 22.04 完整组合包 | 9028842767  | 413,024,597 | `acb0bf24f3c66917f6ecb8fc8b659f3c6a43a61c9cd5b94bff22ff20d92541b9` |
| Ubuntu 22.04 包体测量   | 9028843035  | 7,465       | `fb0b3ce0f95c865e474655e3f2f4640d78649051a5eb1cf9e0af4aa9704d4950` |

| 指标                   | Windows Server 2022                                                | Ubuntu 22.04                                                       |
| ---------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 发布目录 apparent size | 997,349,486 bytes                                                  | 1,086,060,948 bytes                                                |
| 发布目录文件数         | 2,705                                                              | 2,106                                                              |
| 首段完整 smoke         | 15.556 秒                                                          | 13.84 秒                                                           |
| 首段 smoke 峰值内存    | 96,059,392 bytes，约 91.6 MiB                                      | 506,708 KiB，约 494.8 MiB                                          |
| Sidecar SHA-256        | `963f16fc4768109cf10ad6c6d06a15a8d3831befe3babfc98934e296bd442b06` | `6cacaace7bad2d627b7be37ac362cc6acded25d45d7092dfe0a8dc3f2f6cb0fc` |
| 原生依赖               | 打包启动、会话读取与真实索引通过                                   | `ldd` 无缺失依赖                                                   |

Artifact ID、大小、未过期状态和 digest 均由 GitHub Actions API 重新核验。Windows
完整包仍只在 Defender 扫描成功后上传，诊断证据独立保存。

## 剩余验收与下一切片

1. 在 Windows 10 和 Windows 11 产品 VM 上使用 artifact `9028836199` 复验首次
   启动、快速切换会话、重复启动、数据目录、Defender 和退出后残留进程。
2. 后续会话管理切片已实现搜索、重命名和带影响说明的删除；证据见
   [Gate 3 会话管理纵向切片证据](gate-3-session-management-evidence.md)。会话新建和
   固定仍未实现。
3. Composer 仍保持禁用。下一问答切片必须复用 `DocQARuntime.stream_turn()`，并
   同时完成来源范围、流式事件、停止、重试、引用身份、模型配置和凭据边界，不能用
   固定回答或绕过 application service 的 Sidecar 逻辑代替。
4. Gate 3 只有在功能矩阵全部 P0 能力取得自动化或人工证据后才能关闭；本切片通过
   不改变 Gate 3 总体 **In progress** 状态。
