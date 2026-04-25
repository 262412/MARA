# slide-cli Release Flow

`slide-cli` is published as its own Python package and shares the monorepo tag line with its internal runtime packages.

Phase 3 keeps the user-facing shell intentionally split into two lines:

- `slide ...` is the high-permission product shell for runtime commands, app lifecycle, model routing, platform support, and workspace operations, including `slide apply`, `slide export-pdf`, and `slide review`
- `slide docqa ...` is the specialist document-QA line

The canonical top-level commands currently are:

- `slide apply`
- `slide app`
- `slide export-pdf`
- `slide model`
- `slide platform`
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

`slide inspect`, `slide read-slide`, `slide extract`, and `slide search` are the canonical read-only deck-observability commands on the top-level line.

## Version Chain

- Package versions come from git tags through `setuptools-git-versioning`.
- Repository tags follow the `v0.0.x` pattern.
- A tag such as `v0.0.9` produces matching `0.0.9` builds for all Python packages in this repo.

## Publish Order

Release automation publishes packages in dependency order:

1. `ktem`
2. `kotaemon`
3. `slide-cli`
4. `kotaemon-app`

This order is enforced by `scripts/publish_packages.py` and used by `.github/workflows/publish-packages.yaml`.

## Local Release Checks

Build and validate only `slide-cli`:

```shell
python scripts/publish_packages.py release --packages slide-cli --repository testpypi --skip-upload
```

Build and validate the full chain without uploading:

```shell
python scripts/publish_packages.py release --repository testpypi --skip-upload
```

## Packaged Runtime Workflow

The recommended slide user path is to install the public CLI package, initialize the packaged runtime once, and then discover the canonical two-line shell from that environment:

```shell
pip install slide-cli
slide app init
slide app doctor
slide --help
slide doctor
slide docqa --help
```

For a fresh environment, run `slide doctor` first, then use `slide docqa doctor` before your first `slide docqa index`, `slide docqa files`, `slide docqa delete`, `slide docqa ask`, `slide docqa chat`, `slide docqa resume`, or `slide docqa sessions` command.

The same install also exposes the top-level `slide*` skill family plus the specialist `slide-docqa*` skill family under `.codex/skills`, including `slide-docqa-delete`.
`slide docqa acceptance` and `slide docqa check` remain available as maintainer workflows outside the focused DocQA mainline skill family.

The release docs stay with the product shell plus the DocQA specialist line.

## Publish Targets

Manual TestPyPI release:

```shell
python scripts/publish_packages.py release --repository testpypi --skip-existing
```

Manual PyPI release:

```shell
python scripts/publish_packages.py release --repository pypi --skip-existing
```

GitHub Actions can publish the same flow through the `Publish Packages` workflow or automatically on `v*` tags.

## Install Verification

Verify the published package after upload:

```shell
pip install slide-cli
slide doctor
slide --help
```

Or use TestPyPI:

```shell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple slide-cli
```
