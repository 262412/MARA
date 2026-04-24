<a id="top"></a>

<div align="center">

# Slides

A local RAG application repository built around document QA, page-level preview, knowledge graph exploration, and multi-model routing.

Slides is a branded fork of [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon). The original project is licensed under the Apache License 2.0; this fork keeps the original license and attribution while presenting the user-facing product as `slide`. Some internal Python package names remain for compatibility, but users install and operate the CLI through `slide`.

[English](#english) | [中文](#chinese)

[Introduction](#introduction) |
[Key Features](#key-features) |
[Installation](#installation) |
[CLI Document QA](#cli-document-qa) |
[Knowledge Graph And Retrieval](#knowledge-graph-and-retrieval) |
[Customize your application](#customize-your-application) |
[Contribution](#contribution)

</div>

> [Screenshot placeholder: project overview, recommended to show the chat area, document preview area, and the knowledge graph panel on the right]

<!-- start-intro -->

<a id="english"></a>

## English

### Introduction

This repository is not just a single demo page. It is a full document QA runtime that you can run directly, extend in your own codebase, or integrate into terminal-based workflows through the CLI. The current project is built around these core parts:

- A Gradio-based Web UI for document upload, page preview, question answering, citation review, and knowledge graph browsing
- A shared `slide docqa` CLI that uses the same runtime, index, and conversation data as the Web UI
- A `slide model` command group for model routing and environment validation
- A `slide platform` command group for installing Codex / Claude Code platform assets
- A local repository entrypoint in `app.py` and an SSO-oriented entrypoint in `sso_app.py`

The current design goal is to let one configuration, one document index, and one conversation context serve both the browser experience and the CLI experience. You can use this project as a ready-to-run document QA app, or treat it as the foundation for your own RAG application.

#### For end users

- Upload documents in the browser and ask document-level, page-level, or selected-text-focused questions
- Preview PDFs, Office files, and text-based documents inside the app
- Generate a conversation knowledge graph and use graph nodes to shape follow-up questions
- Reuse the same document index and saved conversations through `slide docqa`
- Run local-model or API-model workflows for private or semi-private RAG use cases

#### For developers

- Control runtime behavior, model wiring, and indexing settings through `flowsettings.py`, `.env`, and `modelcli.yml`
- Extend the application-layer UI, DocQA runtime, knowledge graph features, and page preview logic in `libs/ktem`
- Extend the CLI, model routing, and platform support in `libs/kotaemon`
- Use the repository directly for local development, Docker deployment, or assistant-platform integration

### Key Features

- **Shared Web UI and CLI runtime**: the browser UI and `slide docqa` share configuration, file indexes, conversations, and knowledge graph state.
- **Page-level document QA**: the chat page supports page-aware preview and page-scoped context for precise questions such as "What does page 3 say?"
- **Knowledge graph workflow**: the right-side panel can generate or refresh a knowledge graph; graph nodes can pin context and load suggested questions into chat.
- **Fullscreen mindmap viewer**: the knowledge graph includes a preview card and fullscreen viewer with drag-to-pan, wheel zoom, zoom in, zoom out, Fit, and Reset.
- **Multi-format document handling**: the default file collection supports `.png`, `.jpeg`, `.jpg`, `.tiff`, `.tif`, `.pdf`, `.xls`, `.xlsx`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.csv`, `.html`, `.mhtml`, `.txt`, `.md`, and `.zip`.
- **ZIP expansion during indexing**: `docqa index` can accept directories and `.zip` files, and the runtime will extract and continue indexing supported files inside them.
- **Switchable reasoning pipelines**: the default runtime includes `FullQAPipeline`, `FullDecomposeQAPipeline`, `ReAct`, and `ReWOO`.
- **Multi-model and multi-provider support**: the runtime supports OpenAI, Azure OpenAI, Anthropic, Gemini, Cohere, Mistral, VoyageAI, Ollama, and related paths; `modelcli` adds cross-provider routing support.
- **Answer-to-citation linking**: answers can carry citations that are easy to inspect again through the preview area.
- **Multiple startup paths**: the repository supports local source launch, packaged runtime launch, Docker multi-target builds, and optional Google / Keycloak SSO entrypoints.

> [Screenshot placeholder: knowledge graph preview card and fullscreen mindmap viewer]

### Installation

#### System requirements

1. Python 3.10 or newer
2. Docker, if you want to run the project in containers
3. LibreOffice, if you want preview support for `.doc/.docx/.ppt/.pptx/.xls/.xlsx`
4. PDF.js, which is already bundled in this repository by default
5. Provider credentials in `.env` if you want to use API-based models such as OpenAI, Azure OpenAI, Anthropic, Gemini, Cohere, or VoyageAI

#### With Docker (recommended)

This repository includes a multi-stage `Dockerfile` with these targets:

- `lite`
  Good for baseline Web UI / DocQA usage
- `full`
  Adds a more complete document-processing stack, including LibreOffice, Tesseract, and `unstructured`
- `ollama`
  Extends `full` with an embedded Ollama service

Build images:

```bash
docker build --target lite -t kotaemon:lite .
docker build --target full -t kotaemon:full .
docker build --target ollama -t kotaemon:ollama .
```

Run a container:

```bash
docker run \
  -e GRADIO_SERVER_NAME=0.0.0.0 \
  -e GRADIO_SERVER_PORT=7860 \
  -v ./ktem_app_data:/app/ktem_app_data \
  -p 7860:7860 \
  --rm -it \
  kotaemon:full
```

Notes:

- The default entry script is `launch.sh`
- Setting `KH_SSO_ENABLED=true` inside the container switches startup to `sso_app.py`
- Setting `KH_DEMO_MODE=true` switches startup to `sso_app_demo.py`
- If you still need legacy GraphRAG dependencies, add `--build-arg INSTALL_LEGACY_GRAPHRAG=true` during build

After startup, open `http://localhost:7860/`.

#### Without Docker

##### Option 1: install slide without cloning the repo

This is the best path if you want the user-facing product CLI:

```shell
pip install slide-cli
```

The PyPI project is `slide-cli`; it installs the command `slide`. Initialize the runtime once, inspect it with `slide app doctor`, then use the top-level `slide ...` product shell for high-permission workflows and workspace operations such as `slide apply`, `slide export-pdf`, `slide review`, `slide files`, `slide read`, `slide write`, `slide delete`, and `slide shell`, while `slide docqa ...` stays the specialist DocQA line.

Initialize and inspect the runtime:

```shell
slide app init
slide app doctor
```

Start the Web UI:

```shell
slide app run
```

In this mode:

- The runtime manages its own config, data, and cache directories
- `slide app doctor` shows the actual active paths
- `slide docqa ...` reuses the same configuration and data
- `slide app ...`, `slide model ...`, and `slide platform ...` expose app runtime, model routing, and platform support workflows under the same product CLI

##### Option 1b: install the standalone slide CLI from PyPI

This is the same direct package install path, kept here as a quick command reference:

```shell
pip install slide-cli
slide doctor
slide --help
```

If you want to validate the package before a full release, you can install it from TestPyPI:

```shell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple slide-cli
```

`slide-cli`, `ktem`, `kotaemon`, and the legacy app package share the same repository tag version line. A tag such as `v0.0.9` publishes the matching build of each package in dependency order, while `slide-cli` is the public CLI users install.
The release checklist for the standalone CLI lives in [docs/slide_cli_release.md](docs/slide_cli_release.md).

##### Option 2: use the installer scripts in this repo

The repository includes cross-platform installer scripts that create a virtual environment, install dependencies, and run the basic initialization steps.
When the source tree also contains `libs/slide_cli`, these scripts install the standalone `slide` command into the same virtual environment.

macOS / Linux:

```shell
bash install.sh
```

Windows PowerShell:

```powershell
./install.ps1
```

If you also want to install platform assets:

```shell
INSTALL_CODEX=1 bash install.sh
INSTALL_CLAUDE_CODE=1 bash install.sh
```

```powershell
./install.ps1 -InstallCodex
./install.ps1 -InstallClaudeCode
```

After the setup finishes, you can validate the slide agent runtime with:

```shell
slide doctor
```

##### Option 3: source install for local development

This is the right path if you want to modify the repository directly.

1. Create and activate a virtual environment

```shell
python -m venv .venv
```

macOS / Linux:

```shell
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

2. Install the local packages

```shell
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
pip install -e "libs/slide_cli"
```

3. Prepare environment variables

- Copy `.env.example` to `.env`
- Fill in the credentials for the providers you actually use
- If you need Office preview, make sure `soffice` can be discovered, or set `SOFFICE_PATH` explicitly

4. Start the app

```shell
python app.py
```

Validate the slide CLI and inspect the available commands:

```shell
slide doctor
slide --help
```

Source-mode characteristics:

- The repository root `flowsettings.py` is the runtime entry configuration
- Application data is stored locally in `./ktem_app_data`
- This mode is best for debugging UI, knowledge graph, indexing, and reasoning-chain behavior

5. Optional SSO startup path

If you want to wrap Gradio through FastAPI and enable SSO:

```shell
uvicorn sso_app:app --host 0.0.0.0 --port 7860
```

This path reads:

- Google SSO: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Keycloak SSO: `AUTHENTICATION_METHOD=KEYCLOAK`, `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`

### CLI Document QA

`slide docqa` uses the same application runtime, so it shares:

- Runtime configuration
- File indexes
- Conversation and resume capability
- Knowledge graph cache

For a fresh setup, start with:

```shell
slide app init
slide app doctor
slide docqa doctor
```

#### Index documents

Index one file, an entire directory, or zip archives:

```shell
slide docqa index ./docs/report.pdf
slide docqa index ./docs ./archive.zip --reindex
slide docqa files
```

Notes:

- Directories are expanded recursively and filtered by supported file types
- `.zip` files are extracted automatically before indexing
- `--reindex` can replace existing indexed copies

#### Ask one question

Document-level QA:

```shell
slide docqa ask --file report.pdf --prompt "Summarize this document"
```

Page-level QA:

```shell
slide docqa ask --file report.pdf --page 12 --prompt "What does this page say?"
```

Selected-text-focused QA:

```shell
slide docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"
```

You can also pass graph context from disk:

```shell
slide docqa ask --graph-context-file ./graph-context.json --prompt "What should I focus on next?"
```

Common options:

- `--conversation <id>`: continue an existing conversation
- `--file <id-or-name>`: limit retrieval to one or more files
- `--active-file <id-or-name>`: define the active file in multi-file page-level workflows
- `--page <n>`: switch the request into page-level QA
- `--selected-text "..."`: provide an explicit text anchor for retrieval
- `--reasoning <id>`: override the reasoning pipeline for one run
- `--llm <name>`: override the chat model for one run
- `--citation highlight|inline|off`: control citation rendering mode
- `--mindmap`: request mindmap output
- `--json`: return structured JSON

#### Multi-turn sessions

```shell
slide docqa chat --file report.pdf
slide docqa sessions
slide docqa resume <conversation-id>
```

Inside the interactive session, you can use:

- `/files`
- `/use <file>`
- `/page <n>`
- `/page clear`
- `/selected-text <text>`
- `/history`
- `/exit`

#### Acceptance and health checks

```shell
slide docqa acceptance
slide docqa check
```

This runs the end-to-end DocQA acceptance matrix, which is useful after changing indexing, preview, knowledge graph, or CLI behavior.

### CLI Slide Agent

`slide` is the standalone product shell for the packaged slide runtime.

The phase-3 model is intentionally split into two lines:

- `slide ...` for the high-permission product shell
- `slide docqa ...` for the specialist document-QA line

The top-level shell currently centers on:

- `slide app`
- `slide doctor`
- `slide run`
- `slide chat`
- `slide sessions`
- `slide resume`
- `slide inspect`
- `slide read-slide`
- `slide extract`
- `slide search`
- `slide files`
- `slide read`
- `slide write`
- `slide delete`
- `slide shell`
- `slide model`
- `slide platform`

`slide inspect`, `slide read-slide`, `slide extract`, and `slide search` are the canonical read-only deck-observability commands on the top-level line. They sit alongside `slide app ...`, `slide model ...`, `slide platform ...`, and the broader runtime and workspace commands, while `slide docqa ...` remains the specialist document-QA line.

After installing `slide-cli`, start with `slide app init`, `slide app doctor`, `slide --help`, and `slide docqa --help`.

Direct package install:

```shell
pip install slide-cli
```

Start with a runtime check:

```shell
slide doctor
```

To explore the DocQA command group:

```shell
slide docqa --help
slide docqa doctor
```

Codex users get a top-level `slide*` skill family and a specialist `slide-docqa*` skill family under `.codex/skills`.
Claude Code users get matching `slide*` skills plus command wrappers under `.claude/commands`.
Both platform bundles expose the same slide-only support surface: `slide*`, `slide-app*`, `slide-model*`, `slide-platform*`, and `slide-docqa*`.
The focused DocQA family covers the mainline, including `slide-docqa-delete`; `slide docqa acceptance` and `slide docqa check` remain available as maintainer commands.

Example:

```shell
slide --help
slide run --file ./docs/sample.pptx --prompt "Rewrite the opening for executives" --dry-run
slide docqa delete old-document-id
slide docqa ask --file ./docs/sample.pptx --prompt "Summarize this document"
slide docqa files
```

### Knowledge Graph And Retrieval (Default)

The default knowledge graph and retrieval path is built around `FileIndex` and conversation-scoped graph caching:

- `ktem.index.file.FileIndex` is the default file index type
- Uploaded documents, selected files, page context, and graph context all feed into the same QA path
- The knowledge graph is generated per conversation and cached as part of the runtime flow
- If the current sources do not form a single connected graph, the runtime splits them into separate maps

Current knowledge graph workflow:

1. Click `Generate / Refresh Knowledge Graph` in the right-side chat panel
2. The app generates or refreshes a mindmap from the current conversation sources
3. If the uploaded sources belong to disconnected knowledge systems, the status area explains that they are split into separate maps
4. Clicking a graph node updates the `Answer` panel with node summary and a suggested follow-up
5. Clicking `Load into chat` inserts the suggested question into the chat input
6. If you need more space, open the fullscreen graph viewer and use pan, zoom, Fit, and Reset

At the moment, this module works best as a conversation-navigation, follow-up-question, and source-relationship aid rather than a replacement for the main retrieval and answer chain.

#### Legacy GraphRAG Modules (Deprecated)

Legacy GraphRAG families are no longer part of the default runtime path, but compatibility hooks are still present for migration and experimentation.

- `.env.example` still contains legacy GraphRAG variable examples
- The default single-page QA path does not depend on Nano / Light / MS GraphRAG
- To re-enable legacy warnings, set `KH_SHOW_LEGACY_RAG_WARNINGS=true`
- Docker builds can still install old dependencies through `INSTALL_LEGACY_GRAPHRAG=true`

#### Setup Local Models (for local/private RAG)

Start with [docs/local_model.md](docs/local_model.md). The most common local path is Ollama:

```shell
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

Then configure `.env`:

```shell
LOCAL_MODEL=qwen2.5:7b
LOCAL_MODEL_EMBEDDINGS=nomic-embed-text
```

If you want Ollama bundled into the container, use the `ollama` target in the `Dockerfile`.

### Customize your application

#### Runtime layout

- In packaged installs, config, data, and cache directories are managed by `slide app init` and `slide app doctor`
- In source installs, the repository-root `flowsettings.py` is the active entrypoint and local data is written to `./ktem_app_data`
- The default Web UI entrypoint is `app.py`, and the SSO entrypoint is `sso_app.py`

#### Document Preview System

The preview system has two layers: supported upload/index formats, and the actual preview rendering path.

Default file collection support includes:

- `.png`
- `.jpeg`
- `.jpg`
- `.tiff`
- `.tif`
- `.pdf`
- `.xls`
- `.xlsx`
- `.doc`
- `.docx`
- `.ppt`
- `.pptx`
- `.csv`
- `.html`
- `.mhtml`
- `.txt`
- `.md`
- `.zip`

Main preview rendering paths:

- **PDF**: page-level preview through the bundled PDF.js viewer
- **Office documents**: converted to PDF through LibreOffice before preview
- **Text / Markdown / HTML**: shown through paginated text rendering
- **PPT/PPTX**: includes additional presentation-oriented display and zoom handling

The basic page-driven QA relationship looks like this:

```text
Conversation
|-- File A
|   |-- Page 1 -> isolated page-level context
|   |-- Page 2 -> isolated page-level context
|   `-- Page 3 -> isolated page-level context
`-- File B
    |-- Page 1 -> isolated page-level context
    `-- Page 2 -> isolated page-level context
```

That means:

- Changing the current page is not only a display action, it also affects page-level QA context
- The current page, selected text, and graph node context can all influence the answer path together

#### `flowsettings.py`

The workspace [flowsettings.py](flowsettings.py) uses `build_kotaemon_settings(...)` to build the local development runtime:

```python
globals().update(
    build_kotaemon_settings(
        base_dir=this_dir,
        app_data_dir=this_dir / "ktem_app_data",
        docs_dir=this_dir / "docs",
        mode="dev",
    )
)

KH_SETTINGS_SOURCE = "workspace-flowsettings"
```

This is usually the first place to change local default behavior, for example:

- Changing the application data directory
- Adjusting development mode and resource roots
- Taking over the active settings source

#### `.env`

`.env` controls model wiring, credentials, and selected runtime switches. Start from [.env.example](.env.example).

Exposed variables in the current repository include:

- OpenAI: `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDINGS_MODEL`
- Azure OpenAI: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- Cohere / VoyageAI / Mistral
- Local models: `LOCAL_MODEL`, `LOCAL_MODEL_EMBEDDINGS`
- PDF.js: `PDFJS_VERSION_DIST`
- Office preview: `SOFFICE_PATH`
- Authentication: `AUTHENTICATION_METHOD`
- Keycloak: `KEYCLOAK_SERVER_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_SECRET`

If you enable Google SSO, you also need to define:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

#### `modelcli.yml`

If you want to separate model aliases, provider priority, and environment validation into a dedicated config, use `modelcli.yml`:

```shell
slide model init-config --output modelcli.yml
slide model providers --config modelcli.yml
slide model run --prompt "hello" --model gpt-4o-mini --dry-run
```

Useful scenarios:

- Standardizing model aliases across a team
- Quickly checking whether a provider key is available in the environment
- Validating routing behavior before making a real API call

#### Adding your own RAG pipeline

##### Custom Reasoning Pipeline

The default reasoning pipelines currently live in:

- `libs/ktem/ktem/reasoning/simple.py`
- `libs/ktem/ktem/reasoning/react.py`
- `libs/ktem/ktem/reasoning/rewoo.py`

Suggested extension path:

1. Add your implementation under `libs/ktem/ktem/reasoning/`
2. Match the interface and metadata patterns used by the existing reasoning classes
3. Add the dotted path to `KH_REASONINGS`
4. Expose it through the settings system so the UI or CLI can use it

##### Custom Indexing Pipeline

The default file index lives in:

- `libs/ktem/ktem/index/file/`

If you want a new index type, you will usually need to:

1. Add the index implementation
2. Register the type in `KH_INDEX_TYPES`
3. Declare the runtime instance in `KH_INDICES`
4. Connect it to preview, retrieval, conversation, and knowledge graph flows as needed

If you only want to change the behavior of the existing file collection, you usually do not need a brand-new index type. Adjusting the existing `FileIndex` configuration is often enough.

<!-- end-intro -->

## Contribution

If you want to continue developing inside this repository, the recommended path is source-mode development:

```shell
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
pip install -e "libs/slide_cli"
pre-commit install
pytest libs/kotaemon/tests libs/ktem/ktem_tests
```

Good directories to read first:

- [app.py](app.py): local development entrypoint
- [sso_app.py](sso_app.py): SSO wrapper entrypoint
- [libs/kotaemon/kotaemon/cli.py](libs/kotaemon/kotaemon/cli.py): all CLI entrypoints
- [libs/ktem/ktem/docqa](libs/ktem/ktem/docqa): shared DocQA runtime
- [libs/ktem/ktem/pages/chat](libs/ktem/ktem/pages/chat): chat page, page preview, and knowledge graph UI/service code

Before submitting changes, it is a good idea to verify at least:

- `slide app doctor`
- `slide docqa doctor`
- The tests related to your change

If you want fuller collaboration guidance, continue updating [CONTRIBUTING.md](CONTRIBUTING.md).

<p align="right"><a href="#top">Back to top</a> | <a href="#chinese">Jump to 中文</a></p>

---

<a id="chinese"></a>

## 中文

[English](#english) | [中文](#chinese)

[介绍](#zh-introduction) |
[核心功能](#zh-key-features) |
[安装](#zh-installation) |
[CLI 文档问答](#zh-cli-document-qa) |
[知识图谱与检索](#zh-knowledge-graph-and-retrieval) |
[自定义应用](#zh-customize-your-application) |
[参与开发](#zh-contribution)

> [截图占位：项目首页总览，建议展示聊天区、文档预览区和右侧知识图谱区]

<a id="zh-introduction"></a>

### 介绍

这个仓库提供的不是单一页面示例，而是一套可以直接运行、继续二次开发、也可以通过 CLI 接入工作流的完整文档问答运行时。当前项目的核心组成包括：

- 基于 Gradio 的 Web UI，支持文档上传、页面预览、问答、引用回看和知识图谱浏览
- 与 Web UI 共享同一套运行时、索引和会话数据的 `slide docqa` CLI
- 用于多模型路由与环境校验的 `slide model`
- 用于安装 Codex / Claude Code 平台资源的 `slide platform`
- 面向本地仓库开发的 `app.py`、面向 SSO 场景的 `sso_app.py`

这个项目当前的设计重点是“同一份配置、同一份文档索引、同一份会话上下文可以同时服务浏览器端和命令行端”。你既可以把它当成一套现成的文档 QA 应用来用，也可以把它当成自己的 RAG 应用底座继续扩展。

#### 面向使用者

- 通过浏览器上传文档并进行文档级、页级、选中文本级问答
- 在页面预览区查看 PDF、Office 文档和文本文件内容
- 为当前会话生成知识图谱，并基于图谱节点快速构造后续问题
- 在终端中使用 `slide docqa` 复用同一套文档索引和会话
- 使用本地模型或 API 模型运行私有 / 半私有 RAG 流程

#### 面向开发者

- 通过 `flowsettings.py`、`.env` 和 `modelcli.yml` 控制运行时、模型和索引行为
- 在 `libs/ktem` 中扩展应用层 UI、DocQA 运行时、知识图谱和页面预览
- 在 `libs/kotaemon` 中扩展 CLI、多模型路由和平台支持能力
- 用当前仓库直接进行本地开发、Docker 部署或助手平台集成

<a id="zh-key-features"></a>

### 核心功能

- **Web UI + CLI 共用运行时**：浏览器端和 `slide docqa` 共用配置、文件索引、会话与知识图谱状态，避免两套系统分别维护。
- **页面级文档问答**：聊天页支持 page-level 预览和页级上下文，适合“第 3 页写了什么”这类精确问题。
- **知识图谱工作流**：右侧面板可以生成或刷新知识图谱；图谱节点支持选中、挂载上下文，并把推荐问题直接填入聊天框。
- **全屏 Mindmap 浏览器**：知识图谱提供预览卡和全屏查看器，支持拖拽平移、滚轮缩放、放大、缩小、Fit、Reset。
- **多格式文档处理**：默认文件集合支持 `.png`、`.jpeg`、`.jpg`、`.tiff`、`.tif`、`.pdf`、`.xls`、`.xlsx`、`.doc`、`.docx`、`.ppt`、`.pptx`、`.csv`、`.html`、`.mhtml`、`.txt`、`.md`、`.zip`。
- **ZIP 自动展开索引**：`docqa index` 可以直接接收目录和 `.zip` 压缩包，运行时会自动提取其中受支持的文件类型继续索引。
- **可切换的推理管线**：默认内置 `FullQAPipeline`、`FullDecomposeQAPipeline`、`ReAct`、`ReWOO` 四类推理管线。
- **多模型与多提供商接入**：运行时支持 OpenAI、Azure OpenAI、Anthropic、Gemini、Cohere、Mistral、VoyageAI、Ollama 等模型路径；`modelcli` 额外支持跨提供商路由。
- **引用与答案联动**：答案可附带引用，结合文档预览区回看证据位置，便于做基于原文的 QA。
- **多种启动方式**：支持本地源码启动、打包安装启动、Docker 多目标构建，以及可选的 Google / Keycloak SSO 启动入口。

> [截图占位：知识图谱预览卡 + 全屏 Mindmap 查看器]

<a id="zh-installation"></a>

### 安装

#### 系统要求

1. Python 3.10 及以上
2. Docker
   如果你希望通过容器运行项目，则需要 Docker
3. LibreOffice
   如果你需要预览 `.doc/.docx/.ppt/.pptx/.xls/.xlsx`，建议安装 LibreOffice，并在必要时通过 `SOFFICE_PATH` 指向 `soffice`
4. PDF.js
   仓库默认已经带有预构建 PDF.js 资源
5. 模型提供商凭证
   如果你使用 OpenAI、Azure OpenAI、Anthropic、Gemini、Cohere、VoyageAI 等 API，需要在 `.env` 中提供对应密钥

#### 使用 Docker（推荐）

当前仓库自带多阶段 `Dockerfile`，可以直接按目标构建：

- `lite`
  适合基本 Web UI / DocQA 场景
- `full`
  额外包含 LibreOffice、Tesseract、`unstructured` 等更完整的文档处理依赖
- `ollama`
  在 `full` 的基础上内置 Ollama 服务

构建镜像：

```bash
docker build --target lite -t kotaemon:lite .
docker build --target full -t kotaemon:full .
docker build --target ollama -t kotaemon:ollama .
```

运行容器：

```bash
docker run \
  -e GRADIO_SERVER_NAME=0.0.0.0 \
  -e GRADIO_SERVER_PORT=7860 \
  -v ./ktem_app_data:/app/ktem_app_data \
  -p 7860:7860 \
  --rm -it \
  kotaemon:full
```

补充说明：

- 默认入口脚本是 `launch.sh`
- 容器中设置 `KH_SSO_ENABLED=true` 时会切换到 `sso_app.py`
- 容器中设置 `KH_DEMO_MODE=true` 时会切换到 `sso_app_demo.py`
- 如果你需要兼容旧版 GraphRAG 依赖，可以在构建时追加 `--build-arg INSTALL_LEGACY_GRAPHRAG=true`

启动完成后访问 `http://localhost:7860/`。

#### 不使用 Docker

##### 方案 1：不克隆仓库，直接安装打包应用

如果你只是想使用应用，这是最省事的路径：

```shell
pip install slide-cli
```

初始化并检查运行时：

```shell
slide app init
slide app doctor
```

启动 Web UI：

```shell
slide app run
```

这一模式下：

- 配置目录、数据目录、缓存目录由运行时自动管理
- `slide app doctor` 会告诉你实际落盘路径
- `slide docqa ...` 会复用这套配置和数据目录

##### 方案 2：使用仓库自带安装脚本

仓库已经提供了跨平台安装脚本，会自动创建虚拟环境、安装依赖并执行基础初始化。

macOS / Linux:

```shell
bash install.sh
```

Windows PowerShell:

```powershell
./install.ps1
```

如果你还希望顺手安装平台资源：

```shell
INSTALL_CODEX=1 bash install.sh
INSTALL_CLAUDE_CODE=1 bash install.sh
```

```powershell
./install.ps1 -InstallCodex
./install.ps1 -InstallClaudeCode
```

##### 方案 3：源码安装，用于本地开发

如果你准备直接改动仓库代码，这条路径最合适。

1. 创建并激活虚拟环境

```shell
python -m venv .venv
```

macOS / Linux:

```shell
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

2. 安装两个核心包

```shell
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
```

3. 准备环境变量

- 复制 `.env.example` 为 `.env`
- 根据你实际使用的模型提供商填写密钥
- 如果你需要 Office 预览，确认 `soffice` 可执行文件可被找到，或显式设置 `SOFFICE_PATH`

4. 启动应用

```shell
python app.py
```

源码模式特点：

- 当前仓库根目录下的 `flowsettings.py` 会作为运行时配置入口
- 应用数据默认落在本地 `./ktem_app_data`
- 更适合调试 UI、知识图谱、索引和推理链实现

5. 可选的 SSO 启动方式

如果你想通过 FastAPI 包裹 Gradio 并启用 SSO：

```shell
uvicorn sso_app:app --host 0.0.0.0 --port 7860
```

这一路径会读取：

- Google SSO: `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`
- Keycloak SSO: `AUTHENTICATION_METHOD=KEYCLOAK`、`KEYCLOAK_SERVER_URL`、`KEYCLOAK_REALM`、`KEYCLOAK_CLIENT_ID`、`KEYCLOAK_CLIENT_SECRET`

<a id="zh-cli-document-qa"></a>

### CLI 文档问答

`slide docqa` 使用的就是应用运行时本身，因此它和 Web UI 共享：

- 运行时配置
- 文件索引
- 会话与会话恢复能力
- 知识图谱缓存

首次使用建议先检查运行时：

```shell
slide app init
slide app doctor
slide docqa doctor
```

#### 索引文档

索引单个文件、整个目录或压缩包：

```shell
slide docqa index ./docs/report.pdf
slide docqa index ./docs ./archive.zip --reindex
slide docqa files
```

说明：

- 目录会递归展开并索引受支持的文件类型
- `.zip` 会被自动解压并筛选受支持文件
- `--reindex` 可以覆盖已有索引副本

#### 单次提问

文档级问答：

```shell
slide docqa ask --file report.pdf --prompt "Summarize this document"
```

页级问答：

```shell
slide docqa ask --file report.pdf --page 12 --prompt "What does this page say?"
```

选中文本优先问答：

```shell
slide docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"
```

也可以额外传入图谱上下文文件：

```shell
slide docqa ask --graph-context-file ./graph-context.json --prompt "What should I focus on next?"
```

常用参数：

- `--conversation <id>`：接着已有会话继续问
- `--file <id-or-name>`：限制到一个或多个文件
- `--active-file <id-or-name>`：多文件场景下指定当前页级上下文所属文件
- `--page <n>`：切到页级 QA
- `--selected-text "..."`：给检索提供显式文本锚点
- `--reasoning <id>`：临时切换推理管线
- `--llm <name>`：临时切换聊天模型
- `--citation highlight|inline|off`：控制引用输出方式
- `--mindmap`：请求思维导图输出
- `--json`：输出结构化 JSON

#### 多轮会话

```shell
slide docqa chat --file report.pdf
slide docqa sessions
slide docqa resume <conversation-id>
```

交互式会话中支持：

- `/files`
- `/use <file>`
- `/page <n>`
- `/page clear`
- `/selected-text <text>`
- `/history`
- `/exit`

#### 验收与健康检查

```shell
slide docqa acceptance
slide docqa check
```

这会跑完整的 DocQA 验收矩阵，适合在你修改索引、预览、知识图谱或 CLI 之后做回归验证。

#### 模型路由与平台支持

模型路由：

```shell
slide model init-config --output modelcli.yml
slide model providers --config modelcli.yml
slide model run --prompt "health check" --model gpt-4o-mini --dry-run
```

`modelcli` 默认提供 OpenAI、Anthropic、Gemini、OpenRouter 的路由配置模板。

平台支持：

```shell
slide platform list
slide platform install --platform codex --mode full --yes
slide platform install --platform claude-code --mode full --yes
slide platform status --platform codex
slide platform validate
```

这个能力适合把项目附带的技能、命令和平台说明安装到外部 AI coding assistant 环境里。

<a id="zh-knowledge-graph-and-retrieval"></a>

### 知识图谱与检索（默认路径）

当前仓库默认的知识图谱与检索路径围绕 `FileIndex` 和会话级图谱缓存展开：

- `ktem.index.file.FileIndex` 是默认文件索引类型
- 文档上传、文件选择、页级上下文和图谱上下文都会进入同一条 QA 路径
- 知识图谱按会话生成并缓存，不是独立的旁路功能
- 如果当前来源不能组成单一连通图，运行时会自动拆成多个独立 map 展示

当前知识图谱 UI 工作流：

1. 在聊天页右侧点击 `Generate / Refresh Knowledge Graph`
2. 系统根据当前会话来源生成或刷新 Mindmap
3. 如果文档之间存在断开的知识系统，状态区会明确提示它们被拆成多个 map
4. 点击图谱节点后，节点摘要与推荐问题会显示在 `Answer` 面板
5. 点击 `Load into chat` 可以把该问题直接填入聊天输入框
6. 需要更大视图时，可打开全屏图谱查看器并执行平移、缩放、Fit、Reset

这个模块当前更适合作为“会话导航 + 追问入口 + 文档关联理解”工具，而不是替代原本的检索和回答链路。

#### 旧版 GraphRAG 模块（已弃用）

旧版 GraphRAG 家族目前不再是默认运行路径的一部分，但仓库仍保留兼容入口，方便迁移或做实验性回归。

- `.env.example` 中仍保留了 legacy GraphRAG 相关变量示例
- 默认单页 QA 流程不依赖 Nano / Light / MS GraphRAG
- 如果你想重新显示 legacy 提示，可以设置 `KH_SHOW_LEGACY_RAG_WARNINGS=true`
- Docker 构建时可以通过 `INSTALL_LEGACY_GRAPHRAG=true` 安装旧依赖

#### 本地模型配置（用于本地 / 私有 RAG）

推荐从 [docs/local_model.md](docs/local_model.md) 开始。最常见的方式是配合 Ollama：

```shell
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

然后在 `.env` 中配置：

```shell
LOCAL_MODEL=qwen2.5:7b
LOCAL_MODEL_EMBEDDINGS=nomic-embed-text
```

如果你想把 Ollama 一起打进容器，可以直接构建 `Dockerfile` 里的 `ollama` 目标。

<a id="zh-customize-your-application"></a>

### 自定义应用

#### 运行时布局

- 打包安装模式下：配置、数据和缓存目录由 `slide app init` / `slide app doctor` 管理
- 源码模式下：当前仓库根目录的 `flowsettings.py` 是入口，本地数据默认写入 `./ktem_app_data`
- Web UI 默认从 `app.py` 启动，SSO 入口在 `sso_app.py`

#### 文档预览系统

当前项目的预览能力分为“支持上传 / 索引的文件类型”和“实际预览呈现方式”两层。

默认文件集合支持上传和索引：

- `.png`
- `.jpeg`
- `.jpg`
- `.tiff`
- `.tif`
- `.pdf`
- `.xls`
- `.xlsx`
- `.doc`
- `.docx`
- `.ppt`
- `.pptx`
- `.csv`
- `.html`
- `.mhtml`
- `.txt`
- `.md`
- `.zip`

当前主要预览呈现方式：

- **PDF**：通过内置 PDF.js 进行页级预览
- **Office 文档**：通过 LibreOffice 后台转换为 PDF 后预览
- **文本 / Markdown / HTML**：以可分页文本方式展示
- **PPT/PPTX**：带有额外的展示与缩放处理逻辑

Page-driven QA 的基本关系如下：

```text
Conversation
|-- File A
|   |-- Page 1 -> 独立页级上下文
|   |-- Page 2 -> 独立页级上下文
|   `-- Page 3 -> 独立页级上下文
`-- File B
    |-- Page 1 -> 独立页级上下文
    `-- Page 2 -> 独立页级上下文
```

这意味着：

- 页码切换不是纯展示动作，也会影响页级问答上下文
- 当前页、选中文本和图谱节点都可以共同影响回答路径

#### `flowsettings.py`

当前工作区的 [flowsettings.py](flowsettings.py) 使用 `build_kotaemon_settings(...)` 构建本地开发环境的运行时配置：

```python
globals().update(
    build_kotaemon_settings(
        base_dir=this_dir,
        app_data_dir=this_dir / "ktem_app_data",
        docs_dir=this_dir / "docs",
        mode="dev",
    )
)

KH_SETTINGS_SOURCE = "workspace-flowsettings"
```

如果你要改本地仓库的默认行为，通常会先从这里入手，例如：

- 切换应用数据目录
- 改变开发模式与资源根目录
- 接管默认设置来源

#### `.env`

`.env` 负责模型、凭证和部分运行时开关。建议从 [.env.example](.env.example) 开始。

当前仓库已经显式暴露的常见变量包括：

- OpenAI: `OPENAI_API_BASE`、`OPENAI_API_KEY`、`OPENAI_CHAT_MODEL`、`OPENAI_EMBEDDINGS_MODEL`
- Azure OpenAI: `AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_API_KEY`、`OPENAI_API_VERSION`、`AZURE_OPENAI_CHAT_DEPLOYMENT`、`AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- Cohere / VoyageAI / Mistral
- 本地模型: `LOCAL_MODEL`、`LOCAL_MODEL_EMBEDDINGS`
- PDF.js: `PDFJS_VERSION_DIST`
- Office 预览: `SOFFICE_PATH`
- 认证方式: `AUTHENTICATION_METHOD`
- Keycloak: `KEYCLOAK_SERVER_URL`、`KEYCLOAK_CLIENT_ID`、`KEYCLOAK_REALM`、`KEYCLOAK_CLIENT_SECRET`

如果你启用 Google SSO，还需要自行补充：

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

#### `modelcli.yml`

如果你希望把“模型别名 + 提供商优先级 + 环境可用性检查”从应用运行时中拆出来统一管理，可以使用 `modelcli.yml`：

```shell
slide model init-config --output modelcli.yml
slide model providers --config modelcli.yml
slide model run --prompt "hello" --model gpt-4o-mini --dry-run
```

适合的场景：

- 团队内部统一模型别名
- 快速检查某个提供商密钥是否已经注入环境
- 在真正调用 API 前先验证路由是否会落到预期提供商

#### 添加你自己的 RAG 管线

##### 自定义推理管线

当前默认推理管线来自：

- `libs/ktem/ktem/reasoning/simple.py`
- `libs/ktem/ktem/reasoning/react.py`
- `libs/ktem/ktem/reasoning/rewoo.py`

扩展方式建议如下：

1. 在 `libs/ktem/ktem/reasoning/` 下新增你的推理实现
2. 为该实现提供与现有类一致的接口和元信息
3. 把类路径加入 `KH_REASONINGS`
4. 让它通过设置系统暴露到 UI 或 CLI

##### 自定义索引管线

默认文件索引位于：

- `libs/ktem/ktem/index/file/`

如果你要增加新的索引类型，通常需要：

1. 新增索引实现
2. 在运行时把索引类型注册到 `KH_INDEX_TYPES`
3. 在 `KH_INDICES` 中声明实例化配置
4. 处理它与预览、检索、会话和知识图谱的衔接关系

如果你只是想改当前文件集合的行为，往往不需要另起新索引类型，直接调整现有 `FileIndex` 配置就够了。

<a id="zh-contribution"></a>

### 参与开发

如果你要继续在这个仓库上开发，推荐从本地源码模式开始：

```shell
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
pre-commit install
pytest libs/kotaemon/tests libs/ktem/ktem_tests
```

几个最值得先读的目录：

- [app.py](app.py)：本地开发启动入口
- [sso_app.py](sso_app.py)：SSO 包装入口
- [libs/kotaemon/kotaemon/cli.py](libs/kotaemon/kotaemon/cli.py)：所有 CLI 入口
- [libs/ktem/ktem/docqa](libs/ktem/ktem/docqa)：共享 DocQA 运行时
- [libs/ktem/ktem/pages/chat](libs/ktem/ktem/pages/chat)：聊天页、页面预览、知识图谱 UI 与服务

提交改动前建议至少验证：

- `slide app doctor`
- `slide docqa doctor`
- 你改动涉及的测试用例

如果你需要更完整的协作说明，可以继续补充或同步更新 [CONTRIBUTING.md](CONTRIBUTING.md)。

<p align="right"><a href="#top">回到顶部</a> | <a href="#english">Jump to English</a></p>
