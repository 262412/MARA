# slide-cli

Standalone MARA CLI built on top of the existing `kotaemon` and `ktem` libraries.

The phase-3 shell is split into two lines:

- `MARA ...` is the high-permission product line for runtime commands, app lifecycle, model routing, platform support, and workspace operations, including `MARA apply`, `MARA export-pdf`, and `MARA review`
- `MARA docqa ...` is the specialist document-QA line

The top-level line currently centers on:

- `MARA app`
- `MARA model`
- `MARA platform`
- `MARA apply`
- `MARA export-pdf`
- `MARA review`
- `MARA doctor`
- `MARA run`
- `MARA chat`
- `MARA sessions`
- `MARA resume`
- `MARA inspect`
- `MARA read-slide`
- `MARA extract`
- `MARA search`
- `MARA files`
- `MARA read`
- `MARA write`
- `MARA delete`
- `MARA shell`

`MARA inspect`, `MARA read-slide`, `MARA extract`, and `MARA search` are the canonical read-only deck-observability commands on the top-level line. `MARA docqa ...` remains the specialist document-QA line.

## Install

From PyPI:

```shell
pip install slide-cli
```

From TestPyPI:

```shell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple slide-cli
```

From source:

```shell
pip install -e "libs/ktem"
pip install -e "libs/kotaemon[all]"
pip install -e "libs/slide_cli"
```

## Verify

```shell
MARA doctor
MARA --help
MARA docqa --help
```

## Recommended Packaged Runtime Workflow

Install the public CLI package and initialize the packaged runtime once:

```shell
pip install slide-cli
MARA app init
MARA app doctor
MARA doctor
MARA docqa --help
```

Use `MARA docqa doctor` first in a fresh environment, then `MARA docqa index`, `MARA docqa files`, `MARA docqa delete`, `MARA docqa ask`, `MARA docqa chat`, `MARA docqa resume`, and `MARA docqa sessions` as needed.
`MARA docqa acceptance` and `MARA docqa check` stay available as maintainer commands rather than part of the focused slide skill family.

## Examples

```shell
MARA --help
MARA run --file ./docs/sample.pptx --prompt "Rewrite the opening for executives" --dry-run
MARA docqa files
MARA docqa delete old-document-id
MARA docqa ask --file ./docs/sample.pptx --prompt "Summarize this document"
```

## Release Model

This package is published from the monorepo's shared git tag line together with its internal runtime packages.

- Repository tags use the `v0.0.x` pattern.
- Releases publish in dependency order: `ktem -> kotaemon -> slide-cli -> legacy app package`.
- Local release automation is available via `python scripts/publish_packages.py release --packages slide-cli --repository testpypi`.
- A fuller release walkthrough lives in `docs/slide_cli_release.md`.
