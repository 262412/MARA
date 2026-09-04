# MARA Desktop Gate 3 会话新建纵向切片证据

## 结论

功能提交 `9ed01743a3f0205a6396329a2f059f2bc2ae3e94` 已把真实新建任务贯通 React、
Preload、Electron Main、认证 Sidecar 与现有 MARA DocQA runtime。验证提交
`b06056d44fe07d30a7781acd08e4a4b86761e2cc` 还补齐旧故障测试替身的同一 application
service 类型契约；本地端到端、全量 mypy 和静态检查均通过。

[Desktop 31286188463](https://github.com/262412/MARA/actions/runs/31286188463) 已
3/3 成功：Windows Server 2022 与 Ubuntu 22.04 原生打包、smoke 通过，Ubuntu 24.04
对同一 Linux 包的复验也通过；
[Quality gates 31286188580](https://github.com/262412/MARA/actions/runs/31286188580)
也已 20/20 成功。本切片的自动化流水线与证据闭环完成。

本能力仍为 **In progress**：当前版本尚未在 Windows 10/11 产品 VM 上复验，会话固定
不属于本切片。整个 Gate 3 仍有问答、来源、引用、预览、Notes、Studio、Resources、
Settings、Help 和迁移等 P0 能力，不能因本切片通过而标记完成。

## 公共表面与复用边界

- Sidecar 版本提升到 `0.6.0`，增加 `session_create` capability 和认证后的
  `POST /v1/sessions`。请求只接受空 JSON 对象，拒绝额外字段、Origin 和查询参数，并
  要求 1–128 字符的 idempotency key。
- application service 在与 Doctor、Files、Sessions 相同的 runtime 锁内直接调用
  `DocQARuntime.create_session()`，再沿用现有脱敏 Session detail 投影。没有调用
  Click 命令、复制 Gradio callback、改变 `Conversation` schema 或另造会话 ID。
- OpenAPI 生成 `SessionCreateRequest = Record<string, never>`，使 TypeScript 也不能向
  空请求静默加入字段；CI 继续检查 Python schema 与共享类型漂移。
- Preload 只增加 `desktop.createSession()`。Main 使用无参数可信 IPC handler，Renderer
  仍然不知道 Sidecar 端口、令牌或数据路径。
- “新建任务”按钮和 `Ctrl+N` 调用同一能力。React 显示进行中与失败状态，成功后清除
  搜索、切换到真实空会话并刷新左栏。新建与重命名/删除共享写互斥，按钮和快捷键都
  不能绕过该边界。
- Composer 继续禁用，不把空会话误报为已具备问答能力。

## 行为保护与本地验证

现有 Web/CLI 会话、授权和 DocQA CLI 特征测试共 34 项通过。Desktop 没有修改
`MARA` / `MARA-cli` 命令、Click 参数、Gradio 事件链、数据库 schema 或已有会话存储
形状。

| 层级                            | 结果                                                                |
| ------------------------------- | ------------------------------------------------------------------- |
| Web/CLI 会话特征测试            | 34 passed                                                           |
| Application service             | 真实 create、空消息投影和 runtime 复用通过                          |
| Sidecar                         | 48 passed；认证、空参数、幂等、响应、稳定失败与路径脱敏             |
| OpenAPI → TypeScript 漂移检查   | 通过；空对象生成 `Record<string, never>`                            |
| Electron Main/Preload           | 44 passed；明确 IPC、sender、无参数请求和组合包 smoke 断言          |
| React                           | 10 passed；列表四态、新建 pending/failed、真实成功列表和写操作互斥  |
| 打包配置                        | 3 passed                                                            |
| 工作流、供应链与卫生测试        | 48 passed；baseline 未扩大，未刷新 hygiene baseline                 |
| TypeScript 与生产 Renderer 构建 | 通过                                                                |
| 开发态隔离 Gate 3 smoke         | 通过；真实 create → get/list → delete 后再 rename/delete 与索引清理 |

开发态 smoke 使用
`/mnt/fastscratch/users/tbczhang/mara_runtime/gate3-session-create.*` 下的独立临时
Desktop 数据根，输出
`gate3_session_mutation=create_rename_delete status_success`。运行产生 41 个临时文件，
退出后通过受限路径检查完整清理，没有写入旧 `KH_APP_DATA_DIR`。开发 Sidecar 尝试检查
NLTK `punkt_tab` 时记录了 loopback 代理拒绝警告，但所需数据已存在、smoke 成功；原生
组合包使用随包 NLTK 数据验证该边界。

## 跨平台组合包证据

运行 `31286188463` 在 Windows Server 2022 和 Ubuntu 22.04 原生构建相互独立的包，
并将 Ubuntu 22.04 的同一 artifact 复验于 Ubuntu 24.04。三个平台任务均输出
`gate3_session_mutation=create_rename_delete status_success`。该断言要求：

1. 新建返回稳定、不透明的会话 ID 和空消息列表；
2. 随后 `getSession()` 与 `listSessions()` 都能读取该 ID；
3. 响应不含 path、`data_source` 或 user ID；
4. 新建会话可通过真实删除能力清理，并从最终列表消失；
5. 既有 fixture 的重命名、读取和删除回归继续通过。

任一条件失败都会让组合包进程非零退出。当前未过期 artifact 均保存至
2026-11-07：

| artifact                                 | ID           | 上传大小 | SHA-256                                                            |
| ---------------------------------------- | ------------ | -------- | ------------------------------------------------------------------ |
| `mara-desktop-windows`                   | `9029968277` | 395.9 MB | `41c5a14f43419546b4fd90a4f56e24f3adb67037b723f0cb9b159eead581350c` |
| `mara-desktop-windows-defender`          | `9029962290` | 359 B    | `f508360938e3e5933dae2f1bf469910984fb63ebded09f846803e12cdb3b4793` |
| `mara-desktop-windows-smoke-diagnostics` | `9029962101` | 5.5 KB   | `746e54055ed0f8c054b1bec221f37165cbab48463efd010a4bbe9068233847bf` |
| `mara-desktop-linux-22`                  | `9029967024` | 413.0 MB | `b7ba331fdbcfa47ac031e14734eb27b0debe2603a0ae763ec290f1062988a573` |
| `mara-desktop-linux-22-metrics`          | `9029967253` | 7.5 KB   | `e01518a2fe185c70a59a302a5288e57bb11a0f87e7ce26a0e17a25b7913a86d4` |

- Windows 解包后 997,365,786 B、2,705 个文件，组合 smoke 16.529 s，进程峰值
  100,040,704 B；Sidecar SHA-256 为
  `4d17421abc2052a759b8393762349a5367c78a47b716dc3f2fa852a7fb08475a`。
- Ubuntu 22.04 解包后 1,086,077,297 B、2,106 个文件，组合 smoke 14.06 s，最大
  RSS 515,432 KiB；Sidecar SHA-256 为
  `a44c0a715cd1d1da34816ae82f443d0d9967fa10d0ee22586ba096f21ffa6445`，`ldd`
  没有缺失动态库。
- Windows Defender 实时防护和反恶意软件服务开启，移除了 runner 的 `D:\` 整盘
  排除并开启 archive scanning，最终 `scan_result=no_detections`。完整 Windows 包只在
  扫描成功后上传。

## 剩余验收与下一切片

1. 使用本提交产生的 Windows artifact 在 Windows 10 和 Windows 11 产品 VM 上复验
   点击与 `Ctrl+N`、快速重复触发、首次/重复启动、数据目录、Defender 和退出后残留
   进程。
2. 会话固定尚未实现；在确认现有持久化模型或迁移方案前不向 `Conversation` 静默加入
   字段。
3. Composer 仍保持禁用。下一问答切片必须复用 `DocQARuntime.stream_turn()`，并同时
   关闭来源范围、流式事件、停止/重试、引用身份、模型配置和凭据边界，不能以固定回答
   或通用请求接口替代。
4. Gate 3 只有在功能矩阵全部 P0 能力取得自动化或人工验收证据后才能关闭；当前总体
   状态继续为 **In progress**。
