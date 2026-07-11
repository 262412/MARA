# Task 12C2 实施报告

## 1. 状态与提交

Task 12C2 已按 tests-first、security production、façade/refactor/test adaptation、
repository formatting 四层独立提交完成：

- `52d6733 test: specify owner-scoped preview and graph access`
- `a7b8669 security: enforce owner-scoped preview and graph access`
- `a38640e refactor: centralize owner-scoped preview adapters`
- `31227a0 style: satisfy repository verification hooks`

不含本报告提交的 implementation HEAD 为
`31227a0722d5ea2a257be722c7539e5e6a82e9e6`，基线为
`5d46005cd462fa6c3224b960ef60d363a9395343`。

本切片只关闭 owner-aware preview/KG/mindmap 与 Gradio Request identity boundary。
没有修改 F-01、download artifact manifest、notebook CRUD、Settings/UserManagement、
admin、issue report、browser/CSP 或 cache attestation。

## 2. RED -> GREEN 证据

Production 修改前新增并单独提交 4 个 security test 文件，共 24 cases：

- `test_preview_owner_scope.py`
- `test_chat_source_owner_scope.py`
- `test_knowledge_graph_owner_scope.py`
- `test_docqa_owner_preview_scope.py`

首次 RED 结果为 `24 failed`。失败覆盖 victim preview/navigation/timer、tampered path
State、unknown/unauthorized non-disclosure、exact `gr.Request` injection、selector-only
victim、persisted graph victim IDs、Web/DocQA KG、Studio mindmap、DocQA empty page 与
direct-call/timer legacy ABI。实现与 façade 适配后同一 security 集为 `24 passed`。

最终 browser-free focused gate 覆盖 24 个 owner/preview/KG/DocQA/Studio/FileIndex
test files，结果为：

```text
163 passed, 6 warnings in 7.74s
```

自审时另发现 extracted timer helper 对空 legacy `file_name/file_path` 的行为漂移；
先运行新增 regression 得到 `1 failed, 1 passed`，再恢复原先的 empty-state short
circuit，单文件为 `2 passed`，最终已包含在上述 163 cases。

## 3. 实现结果

### Owner-aware DB-to-path boundary

- `PreviewService.resolve_source(s)` 是 Web、DocQA 与 KG 唯一 DB Source-to-path
  boundary；managed/private 查询在 SQL 层同时约束 `Source.id` 与 `Source.user`。
- unknown 与 unauthorized source IDs 均抛相同 `PreviewAccessError` /
  `SOURCE_UNAVAILABLE`，错误不披露文件名、路径或 owner。
- local default 行为保留；private index 即使 local mode 也继续 owner-scoped。
- strict batch resolution 在任何 preview conversion、PDF/page read、Index/docstore graph
  read 前完成；返回的 `ResolvedPreviewSource` 携带已授权 path/name/owner/index metadata。

### Web preview 与 Gradio ABI

- selected、navigation、refresh、restore/page-context 与 timer 都从 `file_id` 和 request
  principal 重新解析 source；客户端 `file_name/file_path` State 不再作为读取依据。
- managed auth 使用 exact `request: gr.Request`，不信任 user component State；local
  direct-call sentinel 保留。
- timer 保留 7-input 与 legacy 8-positional normalization，Request 不成为 component
  input；实际 Gradio 4.39 `special_args` injection tests 通过。
- outputs 保持 selected 14、navigation 10、refresh 7、timer 4、clear 6；named ports、
  `.then/.success` 与 conversation restore/event registration chain 未改。

### Owner-only source graph

- FileIndex/FileSelector、sidebar、selector sync、persist/load graph scope 只使用 owner
  DB rows；DB-visible set 为空时不再回退到 selector State。
- persisted graph IDs 在保存和载入时都与 authenticated owner-visible IDs 相交。
- Web KG、DocQA KG 与 Studio mindmap 在 Index/docstore access 前 strict-resolve 全部
  source IDs，并显式传递 request/runtime resolved user。
- graph dict/schema/cache、Studio outputs 与 artifact shape 保持不变。

### DocQA

- Web turn/session 路径调用 `load_session(..., user_id=resolved_user_id)`；不再把 shared
  runtime default 当 authorization principal。
- selected retrieval records、active filename/page context 与 graph source validation 都
  通过 owner boundary。
- page scope 在 PDF/context 与 fallback 都无文字时抛 typed
  `PreviewContextError(CONTEXT_TEXT_UNAVAILABLE)`，不再静默继续。
- `_DocQAPreviewService` 与 `PreviewSupportService` 只作为 shared core 的 compatibility
  façade；重复 resolver/page-context 实现已删除。

## 4. Public surface 与 changed files

`MARA` / `MARA-cli` commands、CLI options、JSON/DB/session shapes、graph schema/cache、
Studio result shape 与现有成功 UI outputs 均未改变。内部方法只新增 backward-compatible
optional `user_id`/exact Request special parameter；`ktem.preview` 新增 owner access/error
exports。

35 个 changed files 按责任分组：

- preview core：`preview/{__init__,context,errors,service}.py`
- Web preview/KG：`pages/chat/{__init__,page_preview,page_preview_callbacks, page_preview_resolver,chat_knowledge_graph_runtime,knowledge_graph_service, source_scope,studio_artifact_controls,studio_artifact_mindmap}.py`
- DocQA：`docqa/{_runtime_app,_runtime_preview,preview_support,runtime, knowledge_graph}.py`
- owner selectors：`index/file/{_selection,_selector_ui,index}.py`
- tests：`test_{preview_owner_scope,chat_preview_timer,chat_source_owner_scope, chat_source_scope,knowledge_graph_owner_scope,knowledge_graph_service, docqa_owner_preview_scope,docqa_runtime,docqa_runtime_graph_scope, docqa_runtime_helpers,file_index_selection_scope,studio_artifact_failure_scope, studio_artifact_generation,studio_artifact_mindmap}.py`

## 5. Storage 与 quota

实施前 storage preflight：

- repo 位于 `/mnt/scratch/users/tbczhang/projects/MARA-quality-hardening`；
- `.venv` 是指向 `/mnt/fastscratch/users/tbczhang/envs/mara` 的 symlink；
- uv cache、MARA runtime 位于 fastscratch，pre-commit cache 位于 scratch；
- repo root 没有 `data/`、`datasets/`、`outputs/`；
- fastscratch 为 `295.8G` block usage，`471884 / 500000` soft file quota；
- scratch 为 `71.91G` block usage，`472868 / 300000` soft、`500000` hard file
  quota，已处 grace 状态。

测试使用 fresh
`KH_APP_DATA_DIR=/mnt/fastscratch/users/tbczhang/mara_runtime/task12c2-tests-PPuPlB`。
本切片没有依赖安装、模型调用、dataset sync 或大文件下载。后续任何大规模运行仍须先
处理 scratch inode pressure 并复查 fastscratch soft file quota。

## 6. Hygiene 与验证

- focused browser-free relevant gate：`163 passed`，exit 0；
- full `scripts/check_codebase_hygiene.py`：
  `No codebase hygiene ratchet violations.`，exit 0；
- full `pre-commit run --all-files`：全部 hooks 通过，包括 hygiene、Black、isort、
  flake8、autoflake、Prettier、三个 mypy hooks 与 codespell，exit 0；
- changed Python Ruff：`All checks passed!`，exit 0；
- base-to-HEAD `git diff --check`：exit 0；
- final worktree：clean。

没有提高或刷新 `scripts/codebase_hygiene_baseline.json`。最初 ratchet 暴露的
`page_preview.py`、`ChatPage`、FileIndex、KG 和 DocQA runtime growth 通过真实责任提取到
`page_preview_callbacks.py`、`chat_knowledge_graph_runtime.py`、`_runtime_preview.py` 与
`_selection.owner_scope_required` 消除；没有机械压行或新增 large-code exception。

验证期间的非最终错误与 remediation：

- broadened focused gate 初次为 `157 passed, 4 failed`：旧
  `object.__new__(FileIndex)` fixture 缺生产构造器必有的 `_app`；补显式 unmanaged app
  并新增 managed-public owner intersection 后最终 163 passed。
- 第一次 full pre-commit exit 1：Black/isort 格式化文件，mypy 报 6 个新 test-double
  typing errors；格式结果与 test-only monkeypatch/type annotations 独立提交为
  `31227a0`，第二次 full run exit 0。
- 一次 changed-file Ruff shell wrapper 因 `xargs` 前 env 位置错误 exit 127；改为
  `xargs env UV_CACHE_DIR=... uv run ruff check` 后 exit 0。

warnings 仅为 locked dependency 的 cryptography ARC4 与 SWIG deprecations。

## 7. 审查与残余风险

初次自审按 plan alignment、security ordering、type safety、ABI、error handling 与测试
真实性逐项检查；随后 external review 发现一个 DocQA KG cache-before-auth Important
ordering issue，修复证据见第 8 节。由于本 delegated slice 明确禁止再派 subagent，修复
后没有再派独立 reviewer；这是 process-level residual risk，不是已知功能缺陷。

- 按 brief 使用 browser-free tests，未运行 browser/CSP/live UI E2E；Task 12D 负责该
  范围。
- 未运行 live model、LibreOffice 或 backend E2E；本切片验证的是 owner DB boundary、
  callback injection/state tampering、typed context failure 与 graph read ordering。
- scratch inode 已超过 soft quota；后续大型测试/下载存在 quota 风险。
- dependency deprecation warnings 未由本切片引入。

结论：Task 12C2 为 **DONE**，无已知未修复的 security/functional concern；上述仅为
明确的环境、E2E 与独立审查边界。

## 8. External review：DocQA KG cache-before-auth 修复

External review 指出 `docqa/knowledge_graph.py::build_graph` 在 strict owner Source
validation 前调用 `_load_cached_state(conversation_id)`。这会在 victim source 被拒绝前
读取 conversation cache，违反 Task 12C2 的“任何 cache/path/Index/docstore read 前先验证
全部 source IDs”顺序。

修复继续保持 RED 与 production 独立提交：

- `14d6e07 test: authorize DocQA graph sources before cache reads`
- `bbda6a5 security: authorize DocQA graph before cache reads`

RED 单文件结果为 `1 failed, 4 passed`：`_load_cached_state` spy 先抛
`AssertionError(cache read happened before source authorization)`，而测试期望 non-disclosing
`PreviewAccessError`。同一 RED commit 还加入 authorized-source single-resolution
characterization，防止 production 修复先验证一次、graph builder 再查询一次。

Production 只调整 DocQA KG：`build_graph` 先 strict `_load_sources(..., user_id=...)`，成功
后才读 cache，并把已授权 source map 传给 `_build_nodes_and_edges`。graph dict、manifest、
cache schema、save order 与 return shape 不变。安全 test 随后为 `5 passed`；DocQA/Web KG、
owner、runtime graph 与 Studio mindmap focused gate 为 `43 passed`；full hygiene 无 ratchet。

同轮 review 的另一 finding 涉及 Studio `_latest_notebook_artifact` notebook authorization。
Task 12C2 brief 明确把 notebook CRUD authorization 排除在本切片之外，因此本轮未修改该
路径；该 finding 已锁定由 **Task 12F** 实施，避免在 C2 扩大权限与数据模型范围。
