# slide-cli

Standalone slide CLI built on top of the existing `kotaemon` and `ktem` libraries.

The phase-3 shell is split into two lines:

- `slide ...` is the high-permission product line for runtime commands and workspace operations, including `slide apply`, `slide export-pdf`, and `slide review`
- `slide docqa ...` is the specialist document-QA line

The top-level line currently centers on:

- `slide apply`
- `slide export-pdf`
- `slide review`
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

`slide inspect`, `slide read-slide`, `slide extract`, and `slide search` are the canonical read-only deck-observability commands on the top-level line. `slide docqa ...` remains the specialist document-QA line.

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
slide doctor
slide --help
slide docqa --help
```

## Recommended Packaged Runtime Workflow

If you want the packaged Kotaemon runtime alongside the phase-3 slide shell, install the app with the slide extra and initialize it once:

```shell
pip install "kotaemon-app[slide]"
kotaemon app init
kotaemon app doctor
slide doctor
slide docqa --help
```

Use `slide docqa doctor` first in a fresh environment, then `slide docqa index`, `slide docqa files`, `slide docqa delete`, `slide docqa ask`, `slide docqa chat`, `slide docqa resume`, and `slide docqa sessions` as needed.
`slide docqa acceptance` and `slide docqa check` stay available as maintainer commands rather than part of the focused slide skill family.

## Examples

```shell
slide --help
slide run --file ./docs/sample.pptx --prompt "Rewrite the opening for executives" --dry-run
slide docqa files
slide docqa delete old-document-id
slide docqa ask --file ./docs/sample.pptx --prompt "Summarize this document"
```

## Release Model

This package is published from the monorepo's shared git tag line together with `ktem`, `kotaemon`, and `kotaemon-app`.

- Repository tags use the `v0.0.x` pattern.
- Releases publish in dependency order: `ktem -> kotaemon -> slide-cli -> kotaemon-app`.
- Local release automation is available via `python scripts/publish_packages.py release --packages slide-cli --repository testpypi`.
- A fuller release walkthrough lives in `docs/slide_cli_release.md`.
