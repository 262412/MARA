# Getting started with MARA

MARA provides Web, CLI, and Desktop interfaces for working with documents.
Start with the [installation and configuration guide](https://github.com/262412/MARA/blob/Dev/README.md#install-web-and-cli)
([中文](https://github.com/262412/MARA/blob/Dev/README.zh-CN.md#安装-web-与-cli)). It covers the supported Python and uv
versions, the Qdrant service, model configuration, and platform-specific setup.

- Use the [Web and CLI guide](usage.md) to import documents, ask questions,
  inspect citations, and continue saved conversations.
- For Desktop source setup and shared Web/CLI data, see the
  [Desktop overview](desktop/README.md). Packaged previews are listed in
  [MARA releases](https://github.com/262412/MARA/releases).
- Maintainers building a reviewer ZIP should use
  [reviewer installation](reviewer_installation.md).
- Development setup and checks are in [Contributing](development/contributing.md).

Run `MARA app doctor` before importing data. Confirm the effective data directory,
model configuration, and authentication setup. See
[configuration and data](https://github.com/262412/MARA/blob/Dev/README.md#configuration-and-data) for profile sharing
and backup guidance.

Report reproducible problems through [MARA issues](https://github.com/262412/MARA/issues).
