# kotaemon

MARA's core library provides document schemas, readers, model adapters,
embeddings, retrieval, storage, agents, and coding-tool support assets.
`ktem` composes these services into the application, and `mara-research-cli`
exposes the public `MARA` / `MARA-cli` commands.

## Installation and development

Use the [repository installation guide](../../README.md#install-web-and-cli)
with Python 3.11 and the locked runtime. The primary installer keeps workspace
packages non-editable; use the [development guide](../../docs/development/contributing.md)
for source tests and linked worktrees.

MARA selects the `mara-runtime` extra. The older `adv` and `all` extras remain
compatibility aliases for one release and are deprecated; `all` also includes
development tools.
Optional local model backends have their own dependencies.

## Public commands

Shared model routing is available through `MARA model`; coding-tool bundles
are available through `MARA platform`:

```shell
MARA model init-config --output modelcli.yml
MARA model providers --config modelcli.yml
MARA model run --help
MARA platform list
MARA platform validate
```

For application setup, model credentials, and document workflows, use the
[root README](../../README.md). Keep credentials outside Git.
