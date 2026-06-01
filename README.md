<a id="top"></a>

<div align="center">

# MARA

Local-first document QA, knowledge graph exploration, study artifact generation, and multi-model routing.

本地优先的文档问答、知识图谱探索、学习资料生成与多模型路由应用。

MARA is a branded fork of [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon). The fork keeps the upstream Apache License 2.0 attribution while presenting the user-facing product as `MARA`. Internal Python package names such as `kotaemon`, `ktem`, and `slide_cli` remain for compatibility, but the public product commands are `MARA` and `MARA-cli`.

MARA 是基于 [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon) 的品牌化分支，保留 Apache License 2.0 授权与上游归属说明。当前仓库仍保留 `kotaemon`、`ktem`、`slide_cli` 等内部包名以维持兼容性，但用户侧公开产品入口是 `MARA` 与 `MARA-cli`。

[English](#english) | [中文](#中文)

English:
[Overview](#overview) |
[Screenshots](#screenshot-placeholders) |
[Features](#core-capabilities) |
[Quick Start](#quick-start) |
[CLI](#cli-usage) |
[Architecture](#architecture-and-layout) |
[Configuration](#configuration) |
[Development](#development-and-verification) |
[License](#license)

中文:
[项目定位](#项目定位) |
[截图占位](#截图占位) |
[核心能力](#核心能力) |
[快速开始](#快速开始) |
[CLI 使用](#cli-使用) |
[架构与目录](#架构与目录) |
[配置](#配置) |
[开发与验证](#开发与验证) |
[许可](#许可)

</div>

<a id="english"></a>

## English

### Overview

MARA is not a single demo page. It is a runnable local RAG application, a CLI automation surface, and a development base for document-intelligence workflows. The repository is built around one shared runtime:

- A Gradio Web UI for document upload, page preview, grounded chat, citation review, knowledge graph exploration, and Mind Map browsing.
- `MARA docqa`, a document-QA CLI that reuses the same runtime settings, file index, saved conversations, and graph cache as the Web UI.
- The top-level `MARA` CLI for deck workflows, workspace file operations, model routing, platform support assets, and application lifecycle commands.
- `app.py` and `sso_app.py` for source-mode startup and Google / Keycloak SSO startup.
- `benchmark/`, a route-matrix evaluation framework for document format robustness, DocQA routes, MARA agentic reasoning routes, and multimodal evidence tracking.

The main design goal is to let one configuration, one local index, and one conversation store support both browser workflows and terminal workflows. MARA can be used as a ready-to-run local document QA app, or as a foundation for a custom RAG / document intelligence system.

### Screenshot Placeholders

> **Screenshot placeholder: project overview**
> Recommended: show the Web UI with the file area, chat area, document preview, and knowledge graph panel.

> **Screenshot placeholder: document preview and page-level QA**
> Recommended: show a PDF or Office document preview with a question answered against the current page.

> **Screenshot placeholder: knowledge graph / Mind Map**
> Recommended: show the preview card and fullscreen Mind Map viewer after `Generate / Refresh Knowledge Graph`.

> **Screenshot placeholder: MARA DocQA CLI**
> Recommended: show terminal output from `MARA docqa index`, `MARA docqa ask --reasoning mara`, or `MARA docqa artifacts generate`.

> **Screenshot placeholder: benchmark report**
> Recommended: show a generated `report.md`, metrics table, or benchmark output directory.

### Core Capabilities

#### Web UI And Document QA

- Local Gradio Web UI with [app.py](app.py) as the default source-mode entrypoint.
- PDF.js page preview, with Office preview available through LibreOffice-to-PDF conversion.
- Document-level, page-level, multi-document, and selected-text-focused QA.
- Citation-aware answers that can be inspected against the document preview.
- Right-side knowledge graph workflow with generation, refresh, node selection, suggested question loading, and fullscreen Mind Map viewing.
- Optional SSO wrapper in [sso_app.py](sso_app.py) for Google and Keycloak.

#### CLI And Automation

- The `mara-research-cli` package installs the public `MARA` and `MARA-cli` commands.
- Use `MARA ...` for the high-permission product shell and `MARA docqa ...` for the specialist document-QA line.
- `MARA docqa` reuses the application runtime, file index, conversation state, and graph cache.
- Common DocQA commands include `MARA docqa index`, `MARA docqa files`, `MARA docqa delete`, `MARA docqa ask`, `MARA docqa chat`, and `MARA docqa resume`.
- Focused DocQA platform skills include `MARA-docqa-delete` for source removal.
- `MARA app` initializes, checks, and launches the packaged Web UI runtime.
- `MARA model` generates model routing config, checks provider availability, and runs one routed model call.
- `MARA platform` installs and validates Codex / Claude Code support assets.
- The top-level `MARA` line also exposes `MARA inspect`, `MARA read-slide`, `MARA extract`, `MARA search`, `MARA files`, `MARA read`, `MARA write`, `MARA delete`, `MARA shell`, review, and PDF export.

#### MARA Reasoning And Study Artifacts

The default runtime registers these reasoning pipelines:

- `FullQAPipeline`
- `MaraAgentPipeline`
- `FullDecomposeQAPipeline`
- `ReactAgentPipeline`
- `RewooAgentPipeline`

`MARA docqa ask --reasoning mara` can combine task type, agent mode, and artifact type for more structured outputs. Current task types include:

- `qa`
- `summary`
- `compare`
- `explain`
- `study_guide`
- `quiz`
- `flashcards`
- `mindmap`
- `slide_outline`

Saved artifact types include:

- `study_guide`
- `quiz`
- `flashcards`
- `mindmap`
- `slide_outline`

#### Document Formats And Indexing

The default `FileIndex` file collection supports:

```text
.png, .jpeg, .jpg, .tiff, .tif, .pdf, .xls, .xlsx, .doc, .docx,
.ppt, .pptx, .csv, .html, .mhtml, .txt, .md, .zip
```

The runtime creates local directories for application data, file storage, parse cache, OCR cache, Office conversion cache, ZIP extraction cache, vector storage, and document storage. The default setup uses:

- `LanceDBDocumentStore` for document storage.
- `ChromaVectorStore` for vector storage.
- `ktem.index.file.FileIndex` as the default file index type.

#### Models And Providers

The current runtime covers OpenAI, Azure OpenAI, Google Gemini, Anthropic Claude, Groq, Cohere, Mistral, VoyageAI, Ollama, FastEmbed, and local reranking paths. Actual availability depends on your `.env`, local services, and credentials.

`modelcli.yml` separates model aliases, provider priority, and command-line provider checks from the main app runtime.

### Quick Start

#### Option 1: Install The Public CLI Package

Use this path when you want MARA's application and CLI capabilities without editing the source tree.

```shell
pip install mara-research-cli
MARA app init
MARA app doctor
MARA app run
```

For TestPyPI validation, use:

```shell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mara-research-cli
```

After startup, open the local URL printed by Gradio, usually `http://localhost:7860/`.

Useful health checks:

```shell
MARA --help
MARA doctor
MARA docqa doctor
MARA docqa --help
```

#### Option 2: Source Install For Development

Use this path when you want to modify the UI, DocQA runtime, knowledge graph, platform assets, or CLI.

```shell
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```shell
source .venv/bin/activate
```

Install local packages:

```shell
uv sync --extra mara
```

Prepare environment variables:

```shell
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Start the source-mode Web UI:

```shell
python app.py
```

In source mode, root [flowsettings.py](flowsettings.py) is the runtime settings entrypoint, and local app data is written to `./ktem_app_data`.

#### Option 3: Docker

The repository includes a multi-stage [Dockerfile](Dockerfile):

| Target | Purpose |
| --- | --- |
| `lite` | Baseline Web UI / DocQA runtime |
| `full` | Adds LibreOffice, Tesseract, `unstructured`, and other document-processing dependencies |
| `ollama` | Extends `full` with Ollama and pulls `nomic-embed-text` |

Build:

```shell
docker build --target full -t mara:full .
```

Run:

```shell
docker run \
  -e GRADIO_SERVER_NAME=0.0.0.0 \
  -e GRADIO_SERVER_PORT=7860 \
  -v ./ktem_app_data:/app/ktem_app_data \
  -p 7860:7860 \
  --rm -it \
  mara:full
```

Optional startup modes:

- `KH_SSO_ENABLED=true`: start through `sso_app.py`.
- `KH_DEMO_MODE=true`: start through `sso_app_demo.py`.
- `INSTALL_LEGACY_GRAPHRAG=true`: install extra legacy GraphRAG dependencies during the `full` build.

### CLI Usage

#### Public Command Surface

`MARA` and `MARA-cli` point to the same entrypoint. The current public top-level commands are:

| Command | Purpose |
| --- | --- |
| `MARA app` | Packaged app initialization, health checks, and Web UI launch |
| `MARA docqa` | Document QA, indexing, sessions, notes, sources, and artifacts |
| `MARA model` | Model routing config, provider checks, and one routed run |
| `MARA platform` | Codex / Claude Code support asset installation and validation |
| `MARA doctor` | Top-level MARA agent runtime and provider checks |
| `MARA inspect` | Inspect one slide deck |
| `MARA read-slide` | Read one slide summary |
| `MARA extract` | Extract deck or slide text |
| `MARA search` | Search deck summaries |
| `MARA review` | Run deterministic deck review heuristics |
| `MARA export-pdf` | Export a deck to PDF |
| `MARA run` | Execute one high-permission deck workflow |
| `MARA apply` | Apply a saved session patch |
| `MARA chat` / `sessions` / `resume` | Interactive deck-agent sessions |
| `MARA files` / `read` / `write` / `delete` / `shell` | Explicit workspace file and shell operations |

#### DocQA Mainline

Start with runtime checks:

```shell
MARA app doctor
MARA docqa doctor
```

Index files, directories, or ZIP archives:

```shell
MARA docqa index ./docs/report.pdf
MARA docqa index ./docs ./archive.zip --reindex
MARA docqa files
```

Document-level QA:

```shell
MARA docqa ask --file report.pdf --prompt "Summarize this document"
```

Page-level QA:

```shell
MARA docqa ask --file report.pdf --page 12 --prompt "What does this page say?"
```

Selected-text-focused QA:

```shell
MARA docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"
```

MARA reasoning:

```shell
MARA docqa ask \
  --file report.pdf \
  --reasoning mara \
  --agent-mode thorough \
  --task study_guide \
  --artifact study_guide \
  --prompt "Create a source-grounded study guide"
```

Interactive sessions:

```shell
MARA docqa chat --file report.pdf
MARA docqa sessions
MARA docqa resume <conversation-id>
```

Interactive commands:

```text
/files
/use <file>
/page <n>
/page clear
/selected-text <text>
/history
/help
/exit
```

#### Notes, Sources, And Artifacts

MARA's DocQA notebook commands keep conversations, selected sources, notes, and generated artifacts on the same CLI line:

```shell
MARA docqa sources select <conversation-id> --file paper.pdf --file slides.pptx
MARA docqa sources guide <conversation-id>
MARA docqa notes add <conversation-id> --title "Key idea" --text "..."
MARA docqa notes save-answer <conversation-id> --title "Saved answer"
MARA docqa notes convert-source <conversation-id> --note <note-id>
MARA docqa artifacts generate <conversation-id> --type quiz
MARA docqa artifacts list <conversation-id>
MARA docqa artifacts show <conversation-id> --artifact <artifact-id>
```

#### Model Routing

```shell
MARA model init-config --output modelcli.yml
MARA model providers --config modelcli.yml
MARA model run --prompt "health check" --model gpt-4o-mini --dry-run
```

#### Platform Assets

```shell
MARA platform list
MARA platform install --platform codex --mode full --yes
MARA platform install --platform claude-code --mode full --yes
MARA platform status --platform codex
MARA platform validate
```

Platform assets install the repository's MARA skills, commands, and support docs into external AI coding assistant environments such as Codex and Claude Code.

### Architecture And Layout

| Path | Purpose |
| --- | --- |
| [app.py](app.py) | Source-mode Gradio Web UI entrypoint |
| [sso_app.py](sso_app.py) | FastAPI + Gradio SSO entrypoint |
| [flowsettings.py](flowsettings.py) | Source-mode runtime settings entrypoint |
| [libs/ktem](libs/ktem) | Web UI, DocQA runtime, knowledge graph, preview, settings pages, and app-layer behavior |
| [libs/kotaemon](libs/kotaemon) | Core RAG components, loaders, LLM/embedding/reranking integrations, platform assets, and compatibility CLI |
| [libs/slide_cli](libs/slide_cli) | Public `MARA` / `MARA-cli` CLI, DocQA CLI, deck agent, and workspace commands |
| [benchmark](benchmark) | Evaluation framework, manifest normalization, and route-matrix runner |
| [docs](docs) | Usage docs, development docs, release notes, and thesis MVP notes |
| [scripts](scripts) | Release, PDF.js download, codebase hygiene, and maintenance scripts |

Core data flow:

```text
User / CLI / Web UI
        |
        v
MARA runtime settings
        |
        v
FileIndex + local storage + vector store
        |
        v
Reasoning pipeline
        |
        v
Answer + citations + graph context + notebook artifacts
```

### Configuration

#### `.env`

Start from [.env.example](.env.example), then fill only the providers you actually use. Common variables include:

- OpenAI: `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDINGS_MODEL`
- Azure OpenAI: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- Cohere: `COHERE_API_KEY`
- VoyageAI: `VOYAGE_API_KEY`
- Mistral: `MISTRAL_API_KEY`
- Local models: `LOCAL_MODEL`, `LOCAL_MODEL_EMBEDDINGS`, `KH_OLLAMA_URL`
- PDF.js: `PDFJS_VERSION_DIST`
- SSO: `AUTHENTICATION_METHOD`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `KEYCLOAK_SERVER_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_SECRET`

#### `flowsettings.py`

In source mode, [flowsettings.py](flowsettings.py) calls `build_kotaemon_settings(...)` to build MARA runtime settings:

```python
globals().update(
    build_kotaemon_settings(
        base_dir=this_dir,
        app_data_dir=this_dir / "ktem_app_data",
        docs_dir=this_dir / "docs",
        mode="dev",
    )
)
```

Start here when changing the local data directory, development mode, document directory, or default settings source.

#### `modelcli.yml`

[modelcli.yml](modelcli.yml) controls command-line model routing. It is useful for:

- Standardizing model aliases across a team.
- Checking provider credentials before real API calls.
- Supplying routing config to `MARA run` or `MARA model run`.

### Benchmark

The evaluation framework lives in [benchmark](benchmark). It supports normalized manifests, route matrices, DocQA runtime routes, MARA fast / thorough ablations, and metrics for answer quality, citation recall, page hits, multimodal evidence, claim verification, latency, and cache behavior.

Example:

```powershell
python -m benchmark run `
  --manifest benchmark/manifests/format_robustness.json `
  --suite-name format-robustness-v1 `
  --reader-mode default `
  --retrieval-mode hybrid `
  --top-k 5
```

Outputs are written under `benchmark/artifacts/`. See [benchmark/README.md](benchmark/README.md) for manifest and metric details.

### Development And Verification

Non-trivial repository changes must follow [docs/development/codebase-hygiene-contract.md](docs/development/codebase-hygiene-contract.md). Key points:

- Preserve the public `MARA` / `MARA-cli` command surface.
- Do not refresh `scripts/codebase_hygiene_baseline.json` only to make the hygiene gate pass.
- Python changes need the relevant hygiene gate and pre-commit run for affected files.
- CLI, DocQA, Gradio event-chain, persisted-data, and config changes need matching tests.
- Repository-root `pytest -q` is not the default readiness signal while root collection conflicts remain.

README-only changes usually do not need the Python hygiene gate, but should still verify links, public command descriptions, and code accuracy.

#### Maintainer Checks

```powershell
MARA --help
MARA docqa --help
MARA app doctor
MARA docqa doctor
```

When changing the `libs/slide_cli` public command surface:

```powershell
cd libs\slide_cli
uv run --python 3.10 python -m pytest -q
```

When changing the `libs/kotaemon` GitHub Actions unit-test path:

```powershell
cd libs\kotaemon
uv run --python 3.10 python -m pytest -q
```

### Current Boundaries

- Legacy GraphRAG variables and compatibility hooks remain, but the default single-page QA path does not depend on Nano / Light / MS GraphRAG.
- NotebookLM-style notes, sources, and artifacts are present in the CLI; richer Web UI notebook panels remain future work.
- Audio, video, public sharing, cloud sync, and mobile clients are outside the current v1 scope.
- Full PPTX generation remains an extension path; the stable artifact is source-grounded `slide_outline`, alongside existing deck inspection, review, export, and patch-apply capabilities.

### License

This project inherits the upstream Apache License 2.0 license. See [LICENSE.txt](LICENSE.txt) and [NOTICE](NOTICE).

Upstream project:

- [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon)

<p align="right"><a href="#top">Back to top</a> | <a href="#中文">中文</a></p>

<a id="中文"></a>

## 中文

### 项目定位

MARA 不是单页演示应用，而是一套可以本地运行、可以通过 CLI 自动化、也可以继续二次开发的 RAG 应用仓库。它围绕一个共享运行时展开：

- Gradio Web UI：文档上传、页面预览、问答、引用查看、知识图谱与 Mind Map 浏览。
- `MARA docqa`：复用 Web UI 的配置、索引、会话与知识图谱缓存的文档问答 CLI。
- `MARA` 顶层命令：面向演示文稿、工作区文件、模型路由、平台资产安装和应用生命周期的产品 CLI。
- `app.py` / `sso_app.py`：源码模式 Web UI 入口，以及 Google / Keycloak SSO 包装入口。
- `benchmark/`：用于文档格式鲁棒性、DocQA 路由、MARA agentic reasoning 路由与多模态证据的评测框架。

项目当前的设计目标是让同一份配置、同一个文件索引、同一套会话数据同时服务浏览器体验和终端工作流。你可以把它作为一个可运行的本地文档 QA 应用，也可以把它作为自己的 RAG / 文档智能系统基础。

### 截图占位

> **截图占位：项目总览**
> 建议展示 Web UI 主界面，包括左侧文件区域、中间对话区域、右侧文档预览和知识图谱区域。

> **截图占位：文档预览与页面级问答**
> 建议展示 PDF 或 Office 文档的页级预览，并保留一次针对当前页面的问答结果。

> **截图占位：知识图谱 / Mind Map**
> 建议展示 `Generate / Refresh Knowledge Graph` 后的预览卡片和全屏 Mind Map 查看器。

> **截图占位：MARA DocQA CLI**
> 建议展示 `MARA docqa index`、`MARA docqa ask --reasoning mara` 或 `MARA docqa artifacts generate` 的终端输出。

> **截图占位：Benchmark 报告**
> 建议展示一次 `benchmark run` 生成的 `report.md`、指标表或输出目录。

### 核心能力

#### Web UI 与文档问答

- 基于 Gradio 的本地 Web UI，默认入口为 [app.py](app.py)。
- 支持 PDF.js 页面预览；Office 文件可通过 LibreOffice 转换为 PDF 后预览。
- 支持文档级、页级、多文档和选中文本聚焦问答。
- 答案可携带引用信息，便于回到预览区检查证据。
- 右侧知识图谱区域支持生成、刷新、节点选择、建议问题加载和全屏 Mind Map 浏览。
- SSO 入口 [sso_app.py](sso_app.py) 支持 Google 与 Keycloak 配置。

#### CLI 与自动化

- `mara-research-cli` 包安装公开命令 `MARA` 和 `MARA-cli`。
- `MARA docqa` 复用应用运行时、文件索引、会话状态和图谱缓存。
- `MARA app` 管理打包运行时的初始化、健康检查和 Web UI 启动。
- `MARA model` 提供模型路由配置生成、Provider 可用性检查和一次性模型调用。
- `MARA platform` 安装和验证 Codex / Claude Code 平台支持资产。
- `MARA` 顶层还提供幻灯片观察、审阅、PDF 导出、工作区读写和 shell 执行等高权限命令。

#### MARA reasoning 与学习资料

当前默认运行时注册以下推理管线：

- `FullQAPipeline`
- `MaraAgentPipeline`
- `FullDecomposeQAPipeline`
- `ReactAgentPipeline`
- `RewooAgentPipeline`

`MARA docqa ask --reasoning mara` 可以结合任务类型、agent 模式和 artifact 类型生成更结构化的结果。当前 CLI 支持的任务类型包括：

- `qa`
- `summary`
- `compare`
- `explain`
- `study_guide`
- `quiz`
- `flashcards`
- `mindmap`
- `slide_outline`

可保存的学习资料类型包括：

- `study_guide`
- `quiz`
- `flashcards`
- `mindmap`
- `slide_outline`

#### 文档格式与索引

默认 `FileIndex` 文件集合支持以下类型：

```text
.png, .jpeg, .jpg, .tiff, .tif, .pdf, .xls, .xlsx, .doc, .docx,
.ppt, .pptx, .csv, .html, .mhtml, .txt, .md, .zip
```

运行时会为应用数据、文件存储、解析缓存、OCR 缓存、Office 转换缓存、ZIP 展开缓存、向量库和文档库建立本地目录。默认配置中使用：

- `LanceDBDocumentStore` 作为文档存储。
- `ChromaVectorStore` 作为向量存储。
- `ktem.index.file.FileIndex` 作为默认文件索引类型。

#### 模型与 Provider

当前运行时配置覆盖 OpenAI、Azure OpenAI、Google Gemini、Anthropic Claude、Groq、Cohere、Mistral、VoyageAI、Ollama、FastEmbed 以及本地 reranking 相关路径。实际可用性取决于你的 `.env`、本地服务和密钥配置。

`modelcli.yml` 用于独立管理模型别名、Provider 优先级和运行前检查，适合把应用配置与命令行模型路由解耦。

### 快速开始

#### 方式一：安装公开 CLI 包

适合直接使用 MARA 的应用和命令行能力。

```shell
pip install mara-research-cli
MARA app init
MARA app doctor
MARA app run
```

验证 TestPyPI 发布包时使用：

```shell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mara-research-cli
```

启动后访问 Gradio 输出的本地地址，默认通常是 `http://localhost:7860/`。

常用健康检查：

```shell
MARA --help
MARA doctor
MARA docqa doctor
MARA docqa --help
```

#### 方式二：源码开发安装

适合修改 UI、DocQA、知识图谱、平台资产或 CLI。

```shell
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```shell
source .venv/bin/activate
```

安装本地包：

```shell
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
uv sync --extra mara
```

准备环境变量：

```shell
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

启动源码模式 Web UI：

```shell
python app.py
```

源码模式下，根目录 [flowsettings.py](flowsettings.py) 会作为运行时设置入口，本地应用数据默认写入 `./ktem_app_data`。

#### 方式三：Docker

仓库自带多阶段 [Dockerfile](Dockerfile)，主要目标为：

| Target | 用途 |
| --- | --- |
| `lite` | 基础 Web UI / DocQA 运行环境 |
| `full` | 额外包含 LibreOffice、Tesseract、`unstructured` 等文档处理依赖 |
| `ollama` | 在 `full` 基础上安装 Ollama 并预拉取 `nomic-embed-text` |

构建：

```shell
docker build --target full -t mara:full .
```

运行：

```shell
docker run \
  -e GRADIO_SERVER_NAME=0.0.0.0 \
  -e GRADIO_SERVER_PORT=7860 \
  -v ./ktem_app_data:/app/ktem_app_data \
  -p 7860:7860 \
  --rm -it \
  mara:full
```

可选启动模式：

- `KH_SSO_ENABLED=true`：使用 `sso_app.py`。
- `KH_DEMO_MODE=true`：使用 `sso_app_demo.py`。
- `INSTALL_LEGACY_GRAPHRAG=true`：在 `full` 构建阶段安装额外 legacy GraphRAG 依赖。

### CLI 使用

#### 公开命令面

`MARA` 和 `MARA-cli` 指向同一个入口。当前公开顶层命令为：

| 命令 | 说明 |
| --- | --- |
| `MARA app` | 打包应用初始化、健康检查和 Web UI 启动 |
| `MARA docqa` | 文档问答、索引、会话、笔记、资料和 artifacts |
| `MARA model` | 模型路由配置、Provider 检查和一次性运行 |
| `MARA platform` | Codex / Claude Code 平台资产安装与验证 |
| `MARA doctor` | 顶层 MARA agent 运行时和 Provider 检查 |
| `MARA inspect` | 检查一个幻灯片文件的结构摘要 |
| `MARA read-slide` | 读取指定幻灯片页摘要 |
| `MARA extract` | 提取整个 deck 或单页文本 |
| `MARA search` | 在 deck 摘要中搜索文本 |
| `MARA review` | 使用确定性启发式审阅一个 deck |
| `MARA export-pdf` | 将 deck 导出为 PDF |
| `MARA run` | 执行一次高权限 MARA deck 工作流 |
| `MARA apply` | 应用已保存会话中的 patch |
| `MARA chat` / `sessions` / `resume` | 交互式 deck-agent 会话 |
| `MARA files` / `read` / `write` / `delete` / `shell` | 显式工作区文件与 shell 操作 |

#### DocQA 主线

首次使用建议先检查运行时：

```shell
MARA app doctor
MARA docqa doctor
```

索引文件、目录或 ZIP：

```shell
MARA docqa index ./docs/report.pdf
MARA docqa index ./docs ./archive.zip --reindex
MARA docqa files
```

文档级问答：

```shell
MARA docqa ask --file report.pdf --prompt "Summarize this document"
```

页级问答：

```shell
MARA docqa ask --file report.pdf --page 12 --prompt "What does this page say?"
```

选中文本聚焦问答：

```shell
MARA docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"
```

MARA reasoning：

```shell
MARA docqa ask \
  --file report.pdf \
  --reasoning mara \
  --agent-mode thorough \
  --task study_guide \
  --artifact study_guide \
  --prompt "Create a source-grounded study guide"
```

交互式会话：

```shell
MARA docqa chat --file report.pdf
MARA docqa sessions
MARA docqa resume <conversation-id>
```

交互式会话内支持：

```text
/files
/use <file>
/page <n>
/page clear
/selected-text <text>
/history
/help
/exit
```

#### Notes、Sources 与 Artifacts

MARA 的 DocQA notebook 命令把会话、来源选择、笔记和生成资料放在同一条 CLI 线上：

```shell
MARA docqa sources select <conversation-id> --file paper.pdf --file slides.pptx
MARA docqa sources guide <conversation-id>
MARA docqa notes add <conversation-id> --title "Key idea" --text "..."
MARA docqa notes save-answer <conversation-id> --title "Saved answer"
MARA docqa notes convert-source <conversation-id> --note <note-id>
MARA docqa artifacts generate <conversation-id> --type quiz
MARA docqa artifacts list <conversation-id>
MARA docqa artifacts show <conversation-id> --artifact <artifact-id>
```

#### 模型路由

```shell
MARA model init-config --output modelcli.yml
MARA model providers --config modelcli.yml
MARA model run --prompt "health check" --model gpt-4o-mini --dry-run
```

#### 平台资产

```shell
MARA platform list
MARA platform install --platform codex --mode full --yes
MARA platform install --platform claude-code --mode full --yes
MARA platform status --platform codex
MARA platform validate
```

平台资产用于把本仓库附带的 MARA 技能、命令和说明安装到 Codex 或 Claude Code 等外部 AI coding assistant 环境中。

### 架构与目录

| 路径 | 作用 |
| --- | --- |
| [app.py](app.py) | 源码模式 Gradio Web UI 入口 |
| [sso_app.py](sso_app.py) | FastAPI + Gradio SSO 入口 |
| [flowsettings.py](flowsettings.py) | 源码模式运行时设置入口 |
| [libs/ktem](libs/ktem) | Web UI、DocQA runtime、知识图谱、预览、设置页和应用层逻辑 |
| [libs/kotaemon](libs/kotaemon) | 核心 RAG 组件、loader、LLM/embedding/reranking、平台资产和兼容 CLI |
| [libs/slide_cli](libs/slide_cli) | 公开 `MARA` / `MARA-cli` CLI、DocQA CLI、deck agent 和工作区命令 |
| [benchmark](benchmark) | 评测框架、manifest 标准化和 route-matrix 运行器 |
| [docs](docs) | 使用文档、开发文档、发布说明和 thesis MVP 说明 |
| [scripts](scripts) | 发布、PDF.js 下载、代码库卫生检查等维护脚本 |

核心数据流：

```text
User / CLI / Web UI
        |
        v
MARA runtime settings
        |
        v
FileIndex + local storage + vector store
        |
        v
Reasoning pipeline
        |
        v
Answer + citations + graph context + notebook artifacts
```

### 配置

#### `.env`

从 [.env.example](.env.example) 开始，根据实际使用的 Provider 填写密钥。常用变量包括：

- OpenAI：`OPENAI_API_BASE`、`OPENAI_API_KEY`、`OPENAI_CHAT_MODEL`、`OPENAI_EMBEDDINGS_MODEL`
- Azure OpenAI：`AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_API_KEY`、`OPENAI_API_VERSION`、`AZURE_OPENAI_CHAT_DEPLOYMENT`、`AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- Cohere：`COHERE_API_KEY`
- VoyageAI：`VOYAGE_API_KEY`
- Mistral：`MISTRAL_API_KEY`
- 本地模型：`LOCAL_MODEL`、`LOCAL_MODEL_EMBEDDINGS`、`KH_OLLAMA_URL`
- PDF.js：`PDFJS_VERSION_DIST`
- SSO：`AUTHENTICATION_METHOD`、`GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`KEYCLOAK_SERVER_URL`、`KEYCLOAK_CLIENT_ID`、`KEYCLOAK_REALM`、`KEYCLOAK_CLIENT_SECRET`

#### `flowsettings.py`

源码模式下，[flowsettings.py](flowsettings.py) 调用 `build_kotaemon_settings(...)` 生成 MARA 运行时配置：

```python
globals().update(
    build_kotaemon_settings(
        base_dir=this_dir,
        app_data_dir=this_dir / "ktem_app_data",
        docs_dir=this_dir / "docs",
        mode="dev",
    )
)
```

如果需要调整本地数据目录、开发模式、文档目录或默认 settings source，优先从这里入手。

#### `modelcli.yml`

[modelcli.yml](modelcli.yml) 用于命令行模型路由。它适合以下场景：

- 团队统一模型别名。
- 在真实调用 API 前检查 Provider 密钥是否可用。
- 为 `MARA run` 或 `MARA model run` 指定模型路由配置。

### 评测 Benchmark

评测框架位于 [benchmark](benchmark)。它支持统一 manifest、route matrix、DocQA runtime 路由、MARA fast / thorough ablation，以及回答质量、引用召回、页命中、多模态证据、claim verification、延迟与缓存统计等字段。

示例：

```powershell
python -m benchmark run `
  --manifest benchmark/manifests/format_robustness.json `
  --suite-name format-robustness-v1 `
  --reader-mode default `
  --retrieval-mode hybrid `
  --top-k 5
```

输出默认写入 `benchmark/artifacts/`。更多 manifest 与指标说明见 [benchmark/README.md](benchmark/README.md)。

### 开发与验证

本仓库的非平凡改动需要遵守 [docs/development/codebase-hygiene-contract.md](docs/development/codebase-hygiene-contract.md)。重要原则：

- 保持 `MARA` / `MARA-cli` 公开命令面稳定。
- 不为了让卫生检查通过而刷新 `scripts/codebase_hygiene_baseline.json`。
- Python 改动需要按受影响文件运行 hygiene gate 与 pre-commit。
- CLI、DocQA、Gradio 事件链、持久化数据和配置改动需要运行对应测试。
- 根目录 `pytest -q` 不是当前默认 readiness signal，除非已有 collection 冲突被解决。

文档或 README 改动通常不需要运行 Python hygiene gate，但仍应至少确认关键链接、公开命令列表和真实代码保持一致。

#### 维护者常用检查

```powershell
MARA --help
MARA docqa --help
MARA app doctor
MARA docqa doctor
```

当改动 `libs/slide_cli` 的公开命令面时，优先运行：

```powershell
cd libs\slide_cli
uv run --python 3.10 python -m pytest -q
```

当改动 `libs/kotaemon` 的 GitHub Actions 单元测试路径时：

```powershell
cd libs\kotaemon
uv run --python 3.10 python -m pytest -q
```

### 当前边界

- Legacy GraphRAG 相关变量和兼容入口仍保留，但默认单页 QA 路径不依赖 Nano / Light / MS GraphRAG。
- NotebookLM 风格的 notes、sources、artifacts 主线已在 CLI 中落地；更完整的 Web UI notebook 面板仍是后续扩展方向。
- 音频、视频、公共分享、云端同步和移动端不是当前 v1 范围。
- 完整 PPTX 生成仍属于扩展方向；当前稳定产物是 source-grounded `slide_outline` 和已有 deck 观察、审阅、导出、patch 应用能力。

### 许可

本项目继承上游 Apache License 2.0 授权。请参阅 [LICENSE.txt](LICENSE.txt) 与 [NOTICE](NOTICE)。

上游项目：

- [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon)

<p align="right"><a href="#top">回到顶部</a> | <a href="#english">English</a></p>
