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
slide docqa --help
```

## Top-Level Aliases

The canonical DocQA entry point remains `slide docqa ...`, but the following shortcuts are available for quick access:

- `slide ask`
- `slide index`
- `slide files`
- `slide docqa-sessions`
- `slide resume-docqa`

`slide resume` stays reserved for the phase-1 slide-session workflow.

Codex users can also pick up the slide-specific `slide-docqa*` skill family from `.codex/skills`.

## Recommended Packaged Runtime Workflow

If you want the slide CLI to live beside the packaged Kotaemon runtime, install the app with the slide extra and initialize it once:

```shell
pip install "kotaemon-app[slide]"
kotaemon app init
kotaemon app doctor
slide doctor
slide docqa --help
```

Use `slide docqa doctor` first in a fresh environment, then `slide docqa index`, `slide docqa ask`, `slide docqa chat`, and `slide docqa resume` as needed.

## Examples

```shell
slide run --file ./docs/sample.pptx --prompt "Rewrite the opening for executives" --dry-run
slide run --file ./docs/sample.pptx --prompt "Rewrite the opening for executives" --apply
slide chat --file ./docs/sample.pptx
slide docqa ask --file ./docs/sample.pptx --prompt "Summarize this deck"
```

Interactive chat previews deck patches first and confirms before writing. You can apply the latest patch from the REPL with `/apply` or `/apply ./out/deck.rewritten.pptx`.

## Release Model

This package is published from the monorepo's shared git tag line together with `ktem`, `kotaemon`, and `kotaemon-app`.

- Repository tags use the `v0.0.x` pattern.
- Releases publish in dependency order: `ktem -> kotaemon -> slide-cli -> kotaemon-app`.
- Local release automation is available via `python scripts/publish_packages.py release --packages slide-cli --repository testpypi`.
- A fuller release walkthrough lives in `docs/slide_cli_release.md`.
