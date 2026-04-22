# slide-cli

Standalone slide-focused agent CLI built on top of the existing `kotaemon` and `ktem` libraries.

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
```

## Examples

```shell
slide run --file ./docs/sample.pptx --prompt "Rewrite the opening for executives" --dry-run
slide chat --file ./docs/sample.pptx
```

## Release Model

This package is published from the monorepo's shared git tag line together with `ktem`, `kotaemon`, and `kotaemon-app`.

- Repository tags use the `v0.0.x` pattern.
- Releases publish in dependency order: `ktem -> kotaemon -> slide-cli -> kotaemon-app`.
- Local release automation is available via `python scripts/publish_packages.py release --packages slide-cli --repository testpypi`.
- A fuller release walkthrough lives in `docs/slide_cli_release.md`.
