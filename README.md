<div align="center">

# kotaemon

An open-source clean & customizable RAG UI for chatting with your documents. Built with both end users and
developers in mind.

![Preview](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/preview-graph.png)

<a href="https://trendshift.io/repositories/11607" target="_blank"><img src="https://trendshift.io/api/badge/repositories/11607" alt="Cinnamon%2Fkotaemon | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

[Live Demo #1](https://huggingface.co/spaces/cin-model/kotaemon) |
[Live Demo #2](https://huggingface.co/spaces/cin-model/kotaemon-demo) |
[Online Install](https://cinnamon.github.io/kotaemon/online_install/) |
[Colab Notebook (Local RAG)](https://colab.research.google.com/drive/1eTfieec_UOowNizTJA1NjawBJH9y_1nn)

[User Guide](https://cinnamon.github.io/kotaemon/) |
[Developer Guide](https://cinnamon.github.io/kotaemon/development/) |
[Feedback](https://github.com/Cinnamon/kotaemon/issues) |
[Contact](mailto:kotaemon.support@cinnamon.is)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-31013/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
<a href="https://github.com/Cinnamon/kotaemon/pkgs/container/kotaemon" target="_blank">
<img src="https://img.shields.io/badge/docker_pull-kotaemon:latest-brightgreen" alt="docker pull ghcr.io/cinnamon/kotaemon:latest"></a>
![download](https://img.shields.io/github/downloads/Cinnamon/kotaemon/total.svg?label=downloads&color=blue)
<a href='https://huggingface.co/spaces/cin-model/kotaemon-demo'><img src='https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-blue'></a>
<a href="https://hellogithub.com/en/repository/d3141471a0244d5798bc654982b263eb" target="_blank"><img src="https://abroad.hellogithub.com/v1/widgets/recommend.svg?rid=d3141471a0244d5798bc654982b263eb&claim_uid=RLiD9UZ1rEHNaMf&theme=small" alt="Featured｜HelloGitHub" /></a>

</div>

<!-- start-intro -->

## Introduction

This project serves as a functional RAG UI for both end users who want to do QA on their
documents and developers who want to build their own RAG pipeline.

**✨ Enhanced with Page-Driven QA System**: Each page of each file maintains independent chat history, enabling precise page-level questions and answers.
<br>

```yml
+----------------------------------------------------------------------------+
| End users: Those who use apps built with `kotaemon`.                       |
| (You use an app like the one in the demo above)                            |
|     +----------------------------------------------------------------+     |
|     | Developers: Those who built with `kotaemon`.                   |     |
|     | (You have `import kotaemon` somewhere in your project)         |     |
|     |     +----------------------------------------------------+     |     |
|     |     | Contributors: Those who make `kotaemon` better.    |     |     |
|     |     | (You make PR to this repo)                         |     |     |
|     |     +----------------------------------------------------+     |     |
|     +----------------------------------------------------------------+     |
+----------------------------------------------------------------------------+
```

### For end users

- **Clean & Minimalistic UI**: A user-friendly interface for RAG-based QA.
- **Page-Level Chat Isolation**: Each page maintains separate chat history. Ask "What's on page 3?" without context mixing.
- **Advanced Document Preview**: Faithful format preservation for PDF, Office documents with native-like viewing experience.
- **Support for Various LLMs**: Compatible with LLM API providers (OpenAI, AzureOpenAI, Cohere, etc.) and local LLMs (via `ollama` and `llama-cpp-python`).
- **Easy Installation**: Simple scripts to get you started quickly.

### For developers

- **Framework for RAG Pipelines**: Tools to build your own RAG-based document QA pipeline.
- **Customizable UI**: See your RAG pipeline in action with the provided UI, built with <a href='https://github.com/gradio-app/gradio'>Gradio <img src='https://img.shields.io/github/stars/gradio-app/gradio'></a>.
- **Cross-platform CLI profiles**: Install and validate single-repo support bundles for Claude Code and Codex with `kotaemon platform` commands.

## Key Features

- **Host your own document QA (RAG) web-UI**: Support multi-user login, organize your files in private/public collections, collaborate and share your favorite chat with others.

- **🌟 Page-Driven QA System**: Unique page-level conversation isolation. Each page of each file maintains independent chat history. Ask questions like "What's on page 3?" with precise context awareness.

- **📄 Advanced Document Preview**: Clean, minimalistic preview UI for different file types:

  - **PDF Files**: Native PDF.js viewer with smooth scrolling and zooming
  - **Office Documents** (DOC/DOCX, PPT/PPTX, XLS/XLSX): Auto-convert to PDF for faithful format preservation
  - **Text Files** (TXT, MD, HTML): Syntax-highlighted text preview
  - All previews support page-level navigation and question anchoring

- **Organize your LLM & Embedding models**: Support both local LLMs & popular API providers (OpenAI, Azure, Ollama, Groq).

- **Hybrid RAG pipeline**: Sane default RAG pipeline with hybrid (full-text & vector) retriever and re-ranking to ensure best retrieval quality.

- **Advanced citations with document preview**: By default the system will provide detailed citations to ensure the correctness of LLM answers. View your citations (incl. relevant score) directly in the _in-browser PDF viewer_ with highlights. Warning when retrieval pipeline return low relevant articles.

- **Support complex reasoning methods**: Use question decomposition to answer your complex/multi-hop question. Support agent-based reasoning with `ReAct` and `ReWOO` agents.

- **Configurable settings UI**: You can adjust most important aspects of retrieval & generation process on the UI (incl. prompts).

- **Extensible**: Being built on Gradio, you are free to customize or add any UI elements as you like. Also, we aim to support multiple strategies for document indexing & retrieval. `GraphRAG` indexing pipeline is provided as an example.

![Preview](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/preview.png)

## Installation

> If you are not a developer and just want to use the app, please check out our easy-to-follow [User Guide](https://cinnamon.github.io/kotaemon/). Download the `.zip` file from the [latest release](https://github.com/Cinnamon/kotaemon/releases/latest) to get all the newest features and bug fixes.

### System requirements

1. [Python](https://www.python.org/downloads/) >= 3.10
2. [Docker](https://www.docker.com/): optional, if you [install with Docker](#with-docker-recommended)
3. [Unstructured](https://docs.unstructured.io/open-source/installation/full-installation#full-installation) if you want to process files other than `.pdf`, `.html`, `.mhtml`, and `.xlsx` documents. Installation steps differ depending on your operating system. Please visit the link and follow the specific instructions provided there.
4. **LibreOffice** (optional): Required for previewing Office documents (`.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`). Install from [libreoffice.org](https://www.libreoffice.org/download/download/).
   - **Windows**: Default installation path `C:\Program Files\LibreOffice\program\soffice.exe`
   - **Linux**: `sudo apt-get install libreoffice` or `dnf install libreoffice`
   - **macOS**: `brew install --cask libreoffice`
   - Configure via environment variable: `SOFFICE_PATH=/path/to/soffice`

### With Docker (recommended)

1. We support both `lite` & `full` version of Docker images. With `full` version, the extra packages of `unstructured` will be installed, which can support additional file types (`.doc`, `.docx`, ...) but the cost is larger docker image size. For most users, the `lite` image should work well in most cases.

   **Note**: Docker images include LibreOffice for Office document preview. No additional setup required.

   - To use the `full` version.

     ```bash
     docker run \
     -e GRADIO_SERVER_NAME=0.0.0.0 \
     -e GRADIO_SERVER_PORT=7860 \
     -v ./ktem_app_data:/app/ktem_app_data \
     -p 7860:7860 -it --rm \
     ghcr.io/cinnamon/kotaemon:main-full
     ```

   - To use the `full` version with bundled **Ollama** for _local / private RAG_.

     ```bash
     # change image name to
     docker run <...> ghcr.io/cinnamon/kotaemon:main-ollama
     ```

   - To use the `lite` version.

   ```bash
    # change image name to
    docker run <...> ghcr.io/cinnamon/kotaemon:main-lite
   ```

2. We currently support and test two platforms: `linux/amd64` and `linux/arm64` (for newer Mac). You can specify the platform by passing `--platform` in the `docker run` command. For example:

   ```bash
   # To run docker with platform linux/arm64
   docker run \
   -e GRADIO_SERVER_NAME=0.0.0.0 \
   -e GRADIO_SERVER_PORT=7860 \
   -v ./ktem_app_data:/app/ktem_app_data \
   -p 7860:7860 -it --rm \
   --platform linux/arm64 \
   ghcr.io/cinnamon/kotaemon:main-lite
   ```

3. Once everything is set up correctly, you can go to `http://localhost:7860/` to access the WebUI.

4. We use [GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) to store docker images, all images can be found [here.](https://github.com/Cinnamon/kotaemon/pkgs/container/kotaemon)

### Without Docker

#### Option 1: Install the packaged app without cloning the repo

1. Install the runtime with `pip` or `uv`.

   ```shell
   pip install kotaemon-app
   # or
   uv tool install kotaemon-app
   ```

2. Initialize your user config directory and inspect the runtime:

   ```shell
   kotaemon app init
   kotaemon app doctor
   ```

3. Start the packaged Web UI from any directory:

   ```shell
   kotaemon app run
   ```

   - User config is stored in your platform config directory.
   - User data, file storage, and caches are stored in platform-specific data/cache directories.
   - If you need custom defaults, edit the generated `flowsettings.py` in your user config directory and keep secrets in the adjacent `.env`.

#### Option 2: Use the release installer scripts

If you downloaded a release archive instead of cloning the repository, run the bundled installer:

```shell
# macOS / Linux
bash install.sh

# Windows PowerShell
./install.ps1
```

The installer creates a virtual environment, installs the Kotaemon runtime, runs `kotaemon app init`, and leaves you with a ready-to-use `kotaemon` CLI.

#### Option 3: Source install for local development

1. Clone and install required packages on a fresh python environment.

   ```shell
   # optional (setup env)
   conda create -n kotaemon python=3.10
   conda activate kotaemon

   # clone this repo
   git clone https://github.com/Cinnamon/kotaemon
   cd kotaemon

   pip install -e "libs/kotaemon[all]"
   pip install -e "libs/ktem"
   ```

2. Create a `.env` file in the root of this project. Use `.env.example` as a template

   The `.env` file is there to serve use cases where users want to pre-config the models before starting up the app (e.g. deploy the app on HF hub). The file will only be used to populate the db once upon the first run, it will no longer be used in consequent runs.

3. (Optional) To enable in-browser `PDF_JS` viewer, download [PDF_JS_DIST](https://github.com/mozilla/pdf.js/releases/download/v4.0.379/pdfjs-4.0.379-dist.zip) then extract it to `libs/ktem/ktem/assets/prebuilt`

<img src="https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/pdf-viewer-setup.png" alt="pdf-setup" width="300">

4. (Optional) **Office Document Preview Setup**: If you want to preview Office documents (`.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`):

   - Install LibreOffice from [libreoffice.org](https://www.libreoffice.org/download/download/)
   - Verify installation: Run `soffice --version` in terminal
   - Configure path if needed: Set `SOFFICE_PATH` environment variable
   - The system will automatically convert Office files to PDF for faithful format preservation

5. Start the web server:

   ```shell
   python app.py
   ```

   - The app will be automatically launched in your browser.
   - Default username and password are both `admin`. You can set up additional users directly through the UI.

   ![Chat tab](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/chat-tab.png)

6. Check the `Resources` tab and `LLMs and Embeddings` and ensure that your `api_key` value is set correctly from your `.env` file. If it is not set, you can set it there.

### CLI Document QA

Kotaemon also ships with a shared `docqa` CLI that uses the same runtime, settings, indexes,
and saved conversations as the Web UI.

If you installed the packaged app instead of cloning the repository, start with:

```shell
kotaemon app init
kotaemon app doctor
```

Before using the CLI for the first time, make sure your chat model and embedding model are
configured in the app, then validate the runtime:

```shell
kotaemon docqa doctor
```

If you install the Codex or Claude Code platform bundle, DocQA now exposes focused action
entries instead of a single catch-all skill:

- Ask one question -> `kotaemon-docqa-ask` -> `kotaemon docqa ask`
- Index documents -> `kotaemon-docqa-index` -> `kotaemon docqa index`
- Interactive chat -> `kotaemon-docqa-chat` -> `kotaemon docqa chat`
- List indexed files -> `kotaemon-docqa-files` -> `kotaemon docqa files`
- Delete indexed files -> `kotaemon-docqa-delete` -> `kotaemon docqa delete`
- List saved sessions -> `kotaemon-docqa-sessions` -> `kotaemon docqa sessions`
- Resume a conversation -> `kotaemon-docqa-resume` -> `kotaemon docqa resume`
- Runtime health check -> `kotaemon-docqa-doctor` -> `kotaemon docqa doctor`
- Full acceptance check -> `kotaemon-docqa-acceptance` -> `kotaemon docqa acceptance`
- Advanced or mixed workflows -> `kotaemon-docqa` -> any `kotaemon docqa ...` command

Index one or more files into the default file collection:

```shell
kotaemon docqa index ./docs/report.pdf ./docs/appendix.docx
```

List indexed files:

```shell
kotaemon docqa files
```

Run one-shot QA:

```shell
# Whole-document QA (default when --page is omitted)
kotaemon docqa ask --file report.pdf --prompt "Summarize this document"

# Page-level QA (explicit page focus)
kotaemon docqa ask --file report.pdf --page 12 --prompt "What does this page say?"

# Text-focused QA (bias retrieval to an explicit snippet)
kotaemon docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"
```

Important CLI scoping rules:

- Omitting `--page` means whole-document QA.
- Passing `--page <n>` enables page-level QA for that request.
- Passing `--selected-text "..."` focuses retrieval on the provided text without forcing page 1.
- `--file` restricts retrieval to one or more indexed files.
- `--active-file` pins the active file for page-level context when multiple files are selected.

Shared `ask` / `chat` options:

- `--conversation <conversation-id>`: continue an existing saved conversation.
- `--file <file-id-or-name>`: restrict retrieval to one or more indexed files. Repeat the flag to select multiple files.
- `--active-file <file-id-or-name>`: set the active file for page-focused QA when multiple files are selected.
- `--page <n>`: enable page-level QA for one page. If omitted, QA uses the whole document scope.
- `--selected-text "..."`: bias retrieval to an explicit text span without forcing page 1.
- `--graph-context-file <path.json>`: inject graph context from a JSON object on disk.
- `--reasoning <reasoning-id>`: temporarily override the reasoning pipeline.
- `--llm <llm-name>`: temporarily override the chat model.
- `--citation highlight|inline|off`: override citation rendering.
- `--language <language>`: force the answer language for this run.
- `--mindmap`: request mindmap output when supported by the selected reasoning pipeline.
- `--json`: return structured JSON instead of the text UI.

For multi-turn sessions:

```shell
kotaemon docqa chat --file report.pdf
kotaemon docqa sessions
kotaemon docqa resume <conversation-id>
```

Inside `kotaemon docqa chat`, you can use:

- `/files`
- `/use <file>`
- `/page <n>`
- `/page clear`
- `/selected-text <text>`
- `/history`
- `/exit`

To run the full end-to-end acceptance matrix:

```shell
kotaemon docqa acceptance
# or
kotaemon docqa check
```

Other `docqa` command options:

- `kotaemon docqa doctor --json`: inspect runtime health in structured form.
- `kotaemon docqa index <path...> [--reindex] [--json]`: ingest local paths or URLs, optionally replacing existing indexed copies.
- `kotaemon docqa files [--json]`: list indexed files with ids you can reuse in later commands.
- `kotaemon docqa delete <file-id-or-name>... [--json]`: remove indexed files by id or file name.
- `kotaemon docqa sessions [--json]`: list saved CLI/Web conversations.
- `kotaemon docqa resume <conversation-id> [--json]`: reopen an existing interactive conversation.
- `kotaemon docqa acceptance [--keep-artifacts] [--verbose] [--json]`: run the full acceptance matrix, optionally keeping temporary artifacts or surfacing low-level logs.

If you want Codex or Claude Code to expose Kotaemon's bundled skills/commands, install the
platform bundle after the Python packages are installed:

```shell
kotaemon platform install --platform codex --mode full --yes
kotaemon platform install --platform claude-code --mode full --yes
```

### Knowledge Graph And Retrieval (Default)

Kotaemon now uses a unified default retrieval path for single-page QA:

- `FileIndex` is the default and only built-in index in the standard runtime.
- The conversation knowledge graph is generated from uploaded sources and supports interactive node-to-question workflows.
- Selecting files or graph nodes scopes QA through graph context (related file IDs/pages/chunks).

### Legacy GraphRAG Modules (Deprecated)

Legacy GraphRAG families (Nano/Light/MS) are no longer part of the default runtime flow.

- Existing code paths are retained for backward compatibility and custom experimentation.
- Legacy environment variables are deprecated in `.env.example`.
- To re-enable missing-dependency startup warnings for legacy modules, set `KH_SHOW_LEGACY_RAG_WARNINGS=true`.
- In Docker, legacy GraphRAG dependencies are installed only when `INSTALL_LEGACY_GRAPHRAG=true` is passed at build time.

### Setup Local Models (for local/private RAG)

See [Local model setup](docs/local_model.md).

### Customize your application

- In packaged installs, application data lives in your platform-specific user data directory. You can inspect the active paths with `kotaemon app doctor`.
- In source installs, application data is stored in the local `./ktem_app_data` folder. You can back up or copy this folder to transfer your installation to a new machine.

- For advanced users or specific use cases, you can customize these files:

  - `flowsettings.py`
  - `.env`

#### Document Preview System

The application provides advanced document preview capabilities:

**Supported File Types:**

- **PDF Files** (`.pdf`): Native PDF.js viewer with smooth scrolling and zooming
- **Word Documents** (`.doc`, `.docx`): Auto-convert to PDF via LibreOffice
- **PowerPoint Presentations** (`.ppt`, `.pptx`): Auto-convert to PDF via LibreOffice
- **Excel Spreadsheets** (`.xls`, `.xlsx`): Auto-convert to PDF via LibreOffice
- **Text Files** (`.txt`, `.md`, `.html`, `.mhtml`): Syntax-highlighted text preview

**Page-Driven QA Architecture:**

```
Conversation
├── File A
│   ├── Page 1 → Independent chat history
│   ├── Page 2 → Independent chat history
│   └── Page 3 → Independent chat history
└── File B
    ├── Page 1 → Independent chat history
    └── Page 2 → Independent chat history
```

Each page maintains completely isolated conversation history, enabling precise page-specific questions.

#### `flowsettings.py`

This file contains the configuration of your application. You can use the example
[here](flowsettings.py) as the starting point.

<details>

<summary>Notable settings</summary>

```python
# setup your preferred document store (with full-text search capabilities)
KH_DOCSTORE=(Elasticsearch | LanceDB | SimpleFileDocumentStore)

# setup your preferred vectorstore (for vector-based search)
KH_VECTORSTORE=(ChromaDB | LanceDB | InMemory | Milvus | Qdrant)

# Setup your new reasoning pipeline or modify existing one.
KH_REASONINGS = [
    "ktem.reasoning.simple.FullQAPipeline",
    "ktem.reasoning.simple.FullDecomposeQAPipeline",
    "ktem.reasoning.react.ReactAgentPipeline",
    "ktem.reasoning.rewoo.RewooAgentPipeline",
]
```

</details>

#### `.env`

This file provides another way to configure your models and credentials.

<details>

<summary>Configure model via the .env file</summary>

- Alternatively, you can configure the models via the `.env` file with the information needed to connect to the LLMs. This file is located in the folder of the application. If you don't see it, you can create one.

- Currently, the following providers are supported:

  - **OpenAI**

    In the `.env` file, set the `OPENAI_API_KEY` variable with your OpenAI API key in order
    to enable access to OpenAI's models. There are other variables that can be modified,
    please feel free to edit them to fit your case. Otherwise, the default parameter should
    work for most people.

    ```shell
    OPENAI_API_BASE=https://api.openai.com/v1
    OPENAI_API_KEY=<your OpenAI API key here>
    OPENAI_CHAT_MODEL=gpt-3.5-turbo
    OPENAI_EMBEDDINGS_MODEL=text-embedding-ada-002
    ```

  - **Azure OpenAI**

    For OpenAI models via Azure platform, you need to provide your Azure endpoint and API
    key. Your might also need to provide your developments' name for the chat model and the
    embedding model depending on how you set up Azure development.

    ```shell
    AZURE_OPENAI_ENDPOINT=
    AZURE_OPENAI_API_KEY=
    OPENAI_API_VERSION=2024-02-15-preview
    AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-35-turbo
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002
    ```

  - **Local Models**

    - Using `ollama` OpenAI compatible server:

      - Install [ollama](https://github.com/ollama/ollama) and start the application.

      - Pull your model, for example:

        ```shell
        ollama pull llama3.1:8b
        ollama pull nomic-embed-text
        ```

      - Set the model names on web UI and make it as default:

        ![Models](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/models.png)

    - Using `GGUF` with `llama-cpp-python`

      You can search and download a LLM to be ran locally from the [Hugging Face Hub](https://huggingface.co/models). Currently, these model formats are supported:

      - GGUF

        You should choose a model whose size is less than your device's memory and should leave
        about 2 GB. For example, if you have 16 GB of RAM in total, of which 12 GB is available,
        then you should choose a model that takes up at most 10 GB of RAM. Bigger models tend to
        give better generation but also take more processing time.

        Here are some recommendations and their size in memory:

      - [Qwen1.5-1.8B-Chat-GGUF](https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q8_0.gguf?download=true): around 2 GB

        Add a new LlamaCpp model with the provided model name on the web UI.

  </details>

### Adding your own RAG pipeline

#### Custom Reasoning Pipeline

1. Check the default pipeline implementation in [here](libs/ktem/ktem/reasoning/simple.py). You can make quick adjustment to how the default QA pipeline work.
2. Add new `.py` implementation in `libs/ktem/ktem/reasoning/` and later include it in `flowssettings` to enable it on the UI.

#### Custom Indexing Pipeline

- Check sample implementation in `libs/ktem/ktem/index/file/graph`

> (more instruction WIP).

<!-- end-intro -->

## Citation

Please cite this project as

```BibTeX
@misc{kotaemon2024,
    title = {Kotaemon - An open-source RAG-based tool for chatting with any content.},
    author = {The Kotaemon Team},
    year = {2024},
    howpublished = {\url{https://github.com/Cinnamon/kotaemon}},
}
```

## Star History

<a href="https://star-history.com/#Cinnamon/kotaemon&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Cinnamon/kotaemon&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Cinnamon/kotaemon&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Cinnamon/kotaemon&type=Date" />
 </picture>
</a>

## Contribution

Since our project is actively being developed, we greatly value your feedback and contributions. Please see our [Contributing Guide](https://github.com/Cinnamon/kotaemon/blob/main/CONTRIBUTING.md) to get started. Thank you to all our contributors!

<a href="https://github.com/Cinnamon/kotaemon/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Cinnamon/kotaemon" />
</a>
