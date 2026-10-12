# ktem

`ktem` is MARA's application layer: Web UI, shared DocQA services, runtime
configuration, indexing, sessions, previews, and study artifacts. It composes
`kotaemon` services; `mara-research-cli` exposes the public commands.

## Install and run

Use the [repository installation guide](../../README.md#install-web-and-cli)
([中文](../../README.zh-CN.md#安装-web-与-cli)) to prepare Python 3.11, the locked
non-editable packages, Qdrant, and model configuration.

```shell
MARA app init
MARA app doctor
MARA app run
MARA docqa doctor
```

Set the same `MARA_APP_HOME` to share a profile with the CLI and Desktop.
See [configuration and data](../../README.md#configuration-and-data) for path
precedence, existing model records, and backup guidance.

Development setup and verification are in
[Contributing](../../docs/development/contributing.md).
