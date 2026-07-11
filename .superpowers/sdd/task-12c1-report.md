# Task 12C1 实施报告

## 1. 状态与提交

Task 12C1 已按 tests-first、production、ratchet 三个独立提交实施：

- `148e56b test: specify shared preview context consumers`
- `b234e85 refactor: share PDF context and Office conversion`
- `39e3b6c chore: downshift preview conversion hygiene debt`

本切片只实现 no-Gradio PDF/context/service primitives、canonical Office cache、
indexing compatibility policy 与 acceptance delegation。没有修改 Gradio callback、
owner authorization、KG/Studio、notebook、browser/CSP、JSON/DB/session 或 CLI/event ABI。

## 2. RED -> GREEN 证据

RED 在 production 修改前运行。targeted 18 cases 的结果是 4 passed、14 failed：

- 5 个失败：`ktem.preview.pdf` 与 package exports 尚不存在；
- 3 个失败：context/service/canonical API 尚不存在；
- 2 个失败：acceptance 仍直接运行 LibreOffice，未翻译 typed diagnostics；
- 1 个失败：legacy indexing converter 尚未委托 Task 12A core；
- 3 个失败：strict DOCX 静默 fallback、strict DOC 仍抛 `RuntimeError`、non-strict
  未捕获 typed conversion error。

RED tests 随后单独提交为 `148e56b`。实现后的 focused command 为：

```bash
KH_APP_DATA_DIR=/mnt/fastscratch/users/tbczhang/mara_runtime/task12c1-tests \
UV_NO_SYNC=1 uv run --no-sync --python 3.10 python -m pytest -q \
  libs/ktem/ktem_tests/test_preview_pdf_core.py \
  libs/ktem/ktem_tests/test_preview_pdf_compatibility.py \
  libs/ktem/ktem_tests/test_preview_context_service.py \
  libs/ktem/ktem_tests/test_docqa_acceptance_preview.py \
  libs/ktem/ktem_tests/test_office_conversion.py \
  libs/ktem/ktem_tests/test_preview_office_core.py \
  libs/ktem/ktem_tests/test_preview_office_compatibility.py \
  libs/ktem/ktem_tests/test_preview_source_core.py \
  libs/ktem/ktem_tests/test_file_index_page_extraction.py \
  libs/ktem/ktem_tests/test_file_index_office_policy.py
```

结果：`92 passed`。

## 3. 实现结果

### PDF/context/service core

- `PdfService` 对 missing/corrupt/zero-page PDF 抛带 code/stage/path/converter 的
  typed error，不返回假页数。
- page count 与 normalized page text 以 source signature、clamped page、`max_chars`
  缓存；文件 size/mtime signature 变化时清除旧 immutable cache entries。
- `PreviewPurpose` 与 `PageContext` 不含 HTML、Gradio 或 UI state。
- `PreviewService` 对 indexing/acceptance 保持 strict；Web 可返回 fallback context；
  DocQA page context 在 PDF 与 fallback 都无文字时抛 `PreviewContextError`。
- 新 core 由 `ktem.preview` re-export；旧 Web PDF.js URL/query/hash 与
  `ktemfit=pdf|office` 保持 adapter 责任且 characterization 继续通过。

### Canonical Office conversion

- default canonical root 是当前 `KH_OFFICE_PDF_CACHE_DIR`；未显式设置时由当前
  `KH_APP_DATA_DIR/office_pdf_cache_dir` 派生，再使用 locked runtime setting fallback。
- Web/DocQA `OfficePreviewConversionService` 的 strict core 默认写 canonical artifact；
  Web-visible output 仅把已验证 artifact 原子复制到原
  `GRADIO_TEMP_DIR/pdf_previews/<legacy-signature-name>.pdf`。
- 显式 `cache_dir=` 仍保持原 string path 行为。Web/DocQA failure 仍返回空字符串。
- Web、DocQA、indexing façade 与 acceptance-purpose service 的同源测试只调用一次
  real converter；display copy 不会触发第二次 conversion。

### Indexing 与 acceptance

- `ktem.utils.office_conversion` 保留 `OFFICE_EXTENSIONS`、
  `LAYOUT_PRESERVING_OFFICE_EXTENSIONS`、`detect_office_extension`、
  `get_file_signature`、`is_valid_pdf`、`get_office_pdf_cache_dir`、
  `OfficeToPdfConversionService` imports；success 仍返回 string。
- 旧 indexing class 内部只委托 Task 12A `OfficeConversionService`，failure 传播
  typed error。
- strict indexing 对 DOC/DOCX 都传播或构造 typed error；只有
  `KH_OFFICE_TO_PDF_INDEXING_STRICT=False` 才捕获错误并返回 direct-text fallback
  metadata。
- `AcceptanceMatrix._convert_to_pdf` 保留名称与目标 sample path，委托
  `PreviewService(..., purpose=ACCEPTANCE)`；typed code/stage/converter/details 转成
  `AcceptanceFailure`，不再直接调用 `soffice`。

## 4. Public surface 与 changed files

`MARA` / `MARA-cli` command surface、Click options、JSON/DB/session shapes、Gradio
inputs/outputs/order 均无变化。变更文件按责任分组：

- core：`preview/{__init__,errors,office,pdf,context,service}.py`
- compatibility consumers：`utils/office_conversion.py`、
  `index/file/{pipelines,office_policy}.py`、`docqa/acceptance.py`
- tests：`preview_test_utils.py`、PDF/context/acceptance/indexing/Office tests
- ratchet：`scripts/codebase_hygiene_baseline.json`

`test_office_conversion.py` 在 RED commit 后的唯一适配是把 internal
`flowsettings.KH_OFFICE_PDF_CACHE_DIR` monkeypatch 改为公开 canonical env
`KH_OFFICE_PDF_CACHE_DIR`；所有 behavior assertions 保持或加强，没有放宽。

## 5. Storage 与 quota

实施前 preflight：

- `.venv` 是指向 `/mnt/fastscratch/users/tbczhang/envs/mara` 的 symlink；
- Python 解析到 fastscratch 安装；cache/runtime env 在 fastscratch，
  `PRE_COMMIT_HOME=/users/tbczhang/scratch/pre-commit-cache`；
- repo root 没有 `data/`、`datasets/`、`outputs/`；
- fastscratch 为 `295.8G / 500G` soft block quota，`471886 / 500000` soft file quota；
- 全部命令使用 locked environment 与 `uv run --no-sync`，没有安装依赖、模型或数据。

file quota 距 soft limit 约 28114 files，后续长测试/下载仍需先做 preflight。

## 6. Hygiene 与验证

- changed-file hygiene：通过；
- full `scripts/check_codebase_hygiene.py`：通过；
- changed-file pre-commit：通过；
- focused preview/indexing/acceptance：`92 passed`；
- relevant preview/DocQA runtime/file-index/Gradio ABI/runtime-default gate：
  `263 passed`；
- warnings 仅为 locked PyMuPDF SWIG deprecations 与 cryptography ARC4 deprecation；
- commit-range `git diff --check`：通过。

真实 debt removal 后的 baseline downshift：

- `docqa/acceptance.py`: module `862 -> 851`，class `745 -> 732`；
- `index/file/pipelines.py`: module `1027 -> 990`，class `417 -> 401`；
- 删除 `utils/office_conversion.py` 的 `211 lines / 6 non-actionable broad catches`
  baseline entry；新 façade 为 56 行且无 broad catch。

没有提高或全量刷新 baseline。`preview/office.py` 保持 596 行；所有新
module/class/function 均在 600/300/80 budget 内。

## 7. 残余风险与后续边界

- C1 没有把 Web/DocQA controller 的重复 PDF reads 接到 `PdfService`；本切片只提供
  primitives 与 shared Office conversion。controller migration、owner scope、exact
  Gradio request injection、KG/Studio 与 browser hardening 属于 12C2/D。
- 本轮未运行需要 live LibreOffice/model/backend 的端到端 acceptance matrix；unit
  coverage 验证了 delegation、canonical artifact、diagnostic translation 与 output path。
- `PdfService` cache signature 沿用 path/size/mtime_ns contract；消费者若原地替换文件
  但刻意保留全部 metadata，仍可能命中旧 cache，这与现有 source signature contract
  一致，后续若改 content digest 需另行评估 I/O 成本和 cache filename ABI。

## 8. 审查修复（2026-07-11）

### 8.1 提交与 RED -> GREEN

审查修复继续保持 security tests、security production、functional tests、functional
production 独立提交：

- `f292ed0 test: reject unsafe preview artifact targets`
- `11482d3 security: anchor preview artifact publication`
- `4f93c05 test: specify stable lazy PDF preview state`
- `967cd63 fix: stabilize lazy PDF preview state`

Security RED 的 5 个 case 全部失败，分别证明旧 artifact publisher 无法表达可信根与
相对 entry、会跟随 parent/leaf symlink、接受 traversal/absolute target，并会复用同名
但内容不同的有效 PDF。修复后 publisher 把目标锚定到规范化 trusted root，拒绝
symlink/non-regular target，以 SHA-256 比较已有 artifact，并使用同目录临时文件验证后
`os.replace` 发布。

Functional RED 的 7 个 case 全部失败，分别暴露 path replacement 时的二次打开、并发
cache miss 重复解析、三个无界 cache、Office `source_path` 误指 canonical PDF、`~`
cache root 未规范化、package import eager-load PDF/Office/service，以及 DocQA import 链
提前加载 pypdf。生产修复后的同一选择集为 `7 passed`；扩展 PDF/context/cache-root/
Office/security/acceptance/import 集为 `65 passed`。

### 8.2 修复结果与 public surface

- `PdfService` 在单个已打开文件描述符上完成 metadata snapshot、PDF header 检查、
  page count 与目标页取文；路径在调用中被替换时不会把两个文件混成一个结果。
- 同一 signature 的 process-local miss 使用 condition single-flight；count、text 与 path
  signature cache 都是默认上限 128 的 LRU，source signature 变化会淘汰旧值。
- `pypdf.PdfReader` 推迟到实际解析 PDF 时导入；`ktem.preview` 使用 PEP 562 lazy
  exports，原 export 名称保持不变，DocQA preview module import 不再加载 PDF stack。
- Office context 现在保留原 DOC/DOCX `source_path`，同时把 canonical artifact 放在
  `pdf_path`；PDF 输入的既有语义不变。
- 所有 Office/cache roots 都会 expanduser 并转换为 absolute path；trusted cache root
  若是 symlink 或非目录会以 typed artifact error 拒绝。
- `publish_validated_pdf` 的仓库内部调用契约由 `(source, target)` 收紧为
  `(source, trusted_root, entry)`，所有 call sites 已迁移。`PdfService()` 旧构造仍有效，
  只新增可选 keyword `max_cache_entries`。MARA/MARA-cli、Gradio ports/event order、
  PDF.js URL、JSON/DB/session shapes 均未变化。

### 8.3 Fresh verification

最终 relevant command 覆盖全部 `test_preview_*.py`、Gradio preview/timer/submit/
conversation adapters、import laziness、runtime defaults、Office/indexing/acceptance、
DocQA runtime/helpers/graph/pipeline/serialization/session authorization，以及 file-index
extraction/policy/services：`262 passed`，exit 0，15.50 秒。

- full `scripts/check_codebase_hygiene.py`：通过，exit 0；
- `d185d68..967cd63` review range baseline diff：空，未提高或刷新 baseline；
- review-range 10 个 Python files 的 pre-commit：所有 hooks 通过，包括 full hygiene、
  Black、isort、flake8、autoflake、mypy 与 codespell；
- `git diff --check d185d68..967cd63`：通过；
- budgets：`preview/pdf.py` 249 行、`service.py` 336 行、`office.py` 596 行，均在
  600/300/80 contract 内；
- warnings 仍只有既有 PyMuPDF SWIG、cryptography ARC4 deprecation。

验证中有两个已修正的命令错误：第一次 focused command 引用了不存在的
`test_preview_acceptance_core.py`，exit 4；改用实际的
`test_docqa_acceptance_preview.py` 后通过。第一次 changed-file pre-commit 因 Black
格式化 `service.py` 返回 exit 1；按格式化结果复跑后所有 hooks exit 0。

Fresh storage check：repo 位于 scratch，`.venv` 仍解析到
`/mnt/fastscratch/users/tbczhang/envs/mara`；repo root 无 `data/`、`datasets/`、
`outputs/`。fastscratch 当前为 `310176888 / 524288000 KiB` soft block quota，
`471882 / 500000` soft file quota。

### 8.4 残余风险

- single-flight 与 LRU 是进程内状态；跨 worker/process 不共享，但 artifact conversion
  仍使用 Task 12A 的跨进程 coordination。
- PDF snapshot signature 使用 resolved path、device/inode、size、mtime_ns 与 ctime_ns，
  不做整文件 content digest；这避免每次 page access 的全文件 I/O，但特权调用方若能
  同时伪造全部 metadata，理论上仍可制造 cache collision。
- symlink cache root 现在会被明确拒绝；这是防止 trusted-root escape 的有意 hardening，
  使用 symlink 配置的部署需要改为真实目录路径。

## 9. Canonical Office cache attestation 修复（2026-07-11）

第二轮安全复审发现 canonical Office cache 仍会把可预测目标路径上的任意有效 PDF
当作转换结果，并会跟随 leaf symlink。修复继续采用独立 security RED 与 production
提交：

- `56d6416 test: reject poisoned Office preview cache`
- `42d8f0d security: attest canonical Office preview cache`

RED 为 `3 failed, 2 passed`：预置 poison PDF 时 converter 调用数错误地为 0；canonical
leaf symlink 未被拒绝；`_publish` 保留有效但不可信的旧目标。与此同时跨 service 正常
复用和旧 Web-visible `<stem>_<legacy-md5[:12]>.pdf` 文件名保持通过。

修复新增 no-Gradio `CacheAttestationStore`：

- cache 外的运行时 key 以原子 hard-link 竞争发布并强制 0600；
- manifest 绑定 source SHA-256、artifact SHA-256、cache key、绝对 target 与版本，并用
  HMAC-SHA-256 验证；普通 cache-root 写者不能通过篡改摘要字段伪造命中；
- artifact 先原子替换，manifest 最后原子替换；崩溃或任一失配只会导致 cache miss 和
  安全重转换，不会消费未认证 PDF；
- artifact、manifest 与 key 的 symlink/non-regular 形态均以 typed
  `cache_attestation` error 拒绝；
- canonical 和 Web-visible PDF 文件名、跨进程锁、跨实例单次转换以及 string/empty
  compatibility façade 均保持不变。

Fresh verification：安全/core/context/compatibility 集 `48 passed`；完整 Task 12C1
relevant gate `268 passed`（15.33s）；full hygiene、changed-file pre-commit（含 Black、
flake8、mypy）和 range diff-check 全部 exit 0。`preview/office.py` 恰为 600 行，新增
`cache_attestation.py` 为 243 行；新模块/类/函数未超过 600/300/80，baseline 未修改。

实现中扩展并发测试首次暴露 key writer 对 fd 的二次关闭会误关另一线程复用的描述符；
根因修正为 `fdopen` 接管后清空原 descriptor ownership。原子发布 characterization
同步要求 PDF 与 attestation 两个目标都通过原子替换，不再只断言一次 replace。
