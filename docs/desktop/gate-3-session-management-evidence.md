# MARA Desktop Gate 3 会话管理纵向切片证据

## 结论

提交 `42a2817a71ebe74cf8312fea5f11b2945bb801aa` 已把真实会话搜索、重命名和删除
贯通 React、Preload、Electron Main、认证 Sidecar 与现有 MARA DocQA runtime。
[Desktop 运行 31284329278](https://github.com/262412/MARA/actions/runs/31284329278)
在 Windows Server 2022、Ubuntu 22.04 和 Ubuntu 24.04 三个任务全部成功。
同提交的
[Quality gates 31284329391](https://github.com/262412/MARA/actions/runs/31284329391)
共 19 个任务全部成功，没有失败或取消项。

本能力仍为 **In progress**：自动化与 CI 组合包已通过，但该版本尚未在 Windows
10/11 产品 VM 上复验；会话新建和固定也不属于本切片。整个 Gate 3 还有问答、来源、
引用、预览、Notes、Studio、Resources、Settings、Help 和迁移等 P0 能力，不能因
本切片通过而标记完成。

## 公共表面与复用边界

- Sidecar 版本提升到 `0.5.0`，增加 `session_mutations` capability、认证后的
  `PATCH /v1/sessions/{conversation_id}` 和
  `DELETE /v1/sessions/{conversation_id}`。两种写操作都要求 idempotency key，拒绝
  Origin 和查询参数，并使用稳定错误结构。
- 会话 ID 只接受 1–128 个字母、数字、点、下划线或连字符。名称去除首尾空白后
  必须为 1–200 个 Unicode 字符；空白、超长和额外字段都返回 `invalid_request`。
- application service 直接调用现有 `DocQARuntime.rename_session()` 和
  `delete_session()`。缺失或越权会话沿用 runtime 的 owner scope 并投影为
  `session_not_found`；没有调用 Click 命令、复制 Gradio callback 或改变
  `Conversation` schema、字段和 `data_source` 形状。
- Preload 只增加 `desktop.renameSession(sessionId, name)` 和
  `desktop.deleteSession(sessionId)`。Main 再次校验 sender、精确参数数量、不透明 ID
  和名称边界；没有增加通用 invoke、任意 URL、任意文件读取或 Sidecar 凭据暴露。
- 左栏搜索只过滤已经脱敏的真实 Session summaries。重命名使用行内编辑；删除前
  展示“永久删除会话及消息记录、不可撤销”的影响说明。React 覆盖搜索无结果、编辑、
  操作中、失败、重试和原有 loading/success/empty/failed 状态。

## 行为保护与本地验证

现有 Web/CLI 授权特征测试
`libs/ktem/ktem_tests/test_docqa_runtime_session_authorization.py` 共 14 项通过，锁定
owner、public 和跨用户写入边界。Desktop 没有修改 `MARA` / `MARA-cli` 命令、
Click 参数、Gradio 事件链、数据库 schema 或已有会话存储形状。

| 层级                            | 结果                                                             |
| ------------------------------- | ---------------------------------------------------------------- |
| Web/CLI 会话授权特征测试        | 14 passed                                                        |
| Application service             | 真实 rename/delete、404 转换和详情投影通过                       |
| Sidecar                         | 47 passed；认证、参数、幂等、响应、稳定失败与路径脱敏            |
| OpenAPI → TypeScript 漂移检查   | 通过                                                             |
| Electron Main/Preload           | 43 passed；明确 IPC、sender、精确参数、Sidecar 请求与 smoke 断言 |
| React                           | 10 passed；搜索、无结果、编辑、pending、failed 与原有资源状态    |
| 打包配置                        | 3 passed                                                         |
| TypeScript 与生产 Renderer 构建 | 通过                                                             |
| 开发态隔离 Gate 3 smoke         | 通过；真实 rename → get/list → delete → list 与索引/删除均成功   |
| 代码卫生与静态门                | 通过；baseline 未扩大，未刷新 hygiene baseline                   |

开发态 smoke 使用单独的临时 Desktop 数据根，产生 128 个临时文件后完整清理。第一次
启动 fixture 因测试命令缺少 `apps/desktop` 模块路径而以退出码 1 提前停止；修正
`PYTHONPATH` 后原样重跑成功，没有写入现有 `KH_APP_DATA_DIR`。

## 跨平台组合包证据

三个原生/跨版本任务都输出
`gate3_session_mutation=rename_delete status_success`。该断言要求：

1. fixture 会话重命名返回新名称；
2. 随后 `getSession()` 和 `listSessions()` 都读到持久化的新名称；
3. 响应不含 path、`data_source` 或 user ID；
4. 删除只返回 fixture 会话 ID；
5. 再次 `listSessions()` 后该 ID 消失。

任一条件失败都会让组合包进程非零退出。Ubuntu 24.04 下载并复用 Ubuntu 22.04 的
同一包和数据快照，没有重新构建来掩盖 glibc 基线。Windows Defender 诊断实际记录
引擎与反恶意软件服务开启、archive scanning 开启、移除 runner 整盘排除，并得到
`scan_result=no_detections`。

| 平台/产物               | Artifact ID | 压缩大小    | Actions digest                                                     |
| ----------------------- | ----------- | ----------- | ------------------------------------------------------------------ |
| Windows 完整组合包      | 9029407407  | 395,914,394 | `099366aac0aeeef051f844330ce6c7e9584f650c58002cea5d73f3b1857a6b12` |
| Windows smoke 诊断      | 9029401352  | 5,507       | `b47b671bc195cd1ff845a7ba3122fe572e72b7f7f87208285b12b5ad3ef16d14` |
| Windows Defender 诊断   | 9029401485  | 358         | `4540a2575e1fe56b9d262b95c90111270d45b1b74b034653922dc4965c2ee428` |
| Ubuntu 22.04 完整组合包 | 9029403586  | 413,030,388 | `98ebd325a1718bd75f016479b8f588de2d165afa87dc42c4f1fdca706655d274` |
| Ubuntu 22.04 包体测量   | 9029403689  | 7,459       | `56022fbacb4ce2bb418bd666200c073a0c31d08043f082559c9c94b4461edcfb` |

上述 artifact 均未过期，当前到期时间为 2026-11-06。Windows 完整组合包仍只在
Defender 扫描成功后上传，诊断证据独立保留。

| 指标                   | Windows Server 2022                                                | Ubuntu 22.04                                                       |
| ---------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 发布目录 apparent size | 997,362,358 bytes                                                  | 1,086,073,781 bytes                                                |
| 发布目录文件数         | 2,705                                                              | 2,106                                                              |
| 首段完整 smoke         | 16.023 秒                                                          | 14.18 秒                                                           |
| 首段 smoke 峰值内存    | 98,541,568 bytes，约 94.0 MiB                                      | 508,996 KiB，约 497.1 MiB                                          |
| 5 MiB smoke            | 36.889 秒；100,335,616 bytes 峰值                                  | 24.63 秒；638,968 KiB 峰值                                         |
| Sidecar SHA-256        | `89a2f04fa18b33cfa05a74c91ec0fa18337581206e1b87f8fea01f80119ad377` | `38e7704ee5edec2edc2cefce080b060efe17a89f4d3401f9562cfb67c00bd4a1` |
| 原生依赖               | 打包启动、会话变更与全套 smoke 通过                                | `ldd` 无缺失依赖                                                   |

## 剩余验收与下一切片

1. 在 Windows 10 和 Windows 11 产品 VM 上使用 artifact `9029407407` 复验搜索、
   重命名、删除确认、首次/重复启动、数据目录、Defender 和退出后残留进程。
2. 会话新建与固定仍未实现；“新建任务”保持禁用并明确说明将在问答切片开放，不提供
   无行为的伪入口。
3. Composer 仍保持禁用。下一问答切片必须复用 `DocQARuntime.stream_turn()`，并
   同时关闭来源范围、流式事件、停止/重试、引用身份、模型配置和凭据边界，不能以
   固定回答或通用请求接口替代。
4. Gate 3 只有在功能矩阵全部 P0 能力取得自动化或人工验收证据后才能关闭；当前
   总体状态继续为 **In progress**。
