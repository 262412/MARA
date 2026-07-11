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
