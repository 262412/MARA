# ktem

`ktem` is the application/runtime layer for Kotaemon.

It contains the shared Web UI runtime, DocQA runtime, settings bootstrap, packaged
launch helpers, database models, indexing orchestration, page preview services,
and other app-facing components that sit on top of the lower-level `kotaemon`
library.

## Relationship to the other packages

- `kotaemon`: core building blocks for LLMs, embeddings, retrieval, indexing, and platform assets.
- `ktem`: application runtime and UI/service layer that assembles those building blocks into the Kotaemon app.
- `kotaemon-app`: thin top-level installer package that depends on both `ktem` and `kotaemon`.

## Install

For end users, prefer the top-level package:

```bash
pip install kotaemon-app
```

For local development from source:

```bash
pip install -e "libs/kotaemon[all]"
pip install -e "libs/ktem"
```

## Packaged runtime entrypoints

After installing `kotaemon-app`, the shared CLI is available:

```bash
kotaemon app init
kotaemon app doctor
kotaemon app run
kotaemon docqa doctor
```

## Source repository

Project homepage and source:

- https://github.com/Cinnamon/kotaemon
