# ktem

`ktem` is the application/runtime layer for the slide product.

It contains the shared Web UI runtime, DocQA runtime, settings bootstrap, packaged
launch helpers, database models, indexing orchestration, page preview services,
and other app-facing components that sit on top of the lower-level `kotaemon`
library.

## Relationship to the other packages

- `kotaemon`: internal core building blocks for LLMs, embeddings, retrieval, indexing, and platform assets.
- `ktem`: application runtime and UI/service layer that assembles those building blocks into the slide app.
- `slide-cli`: public user-facing CLI package that exposes the `slide` command.

## Install

For end users, prefer the public CLI package:

```bash
pip install slide-cli
```

For local development from source:

```bash
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
```

## Packaged runtime entrypoints

After installing `slide-cli`, the shared CLI is available:

```bash
slide app init
slide app doctor
slide app run
slide docqa doctor
```

## Source repository

Project homepage and source:

- https://github.com/Cinnamon/kotaemon
