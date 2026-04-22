# slide-cli Release Flow

`slide-cli` is published as its own Python package and shares the monorepo tag line with `ktem`, `kotaemon`, and `kotaemon-app`.

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

The recommended slide DocQA user path is to install the packaged runtime with the slide extra, initialize it once, and then discover the canonical `slide docqa ...` command group from that environment:

```shell
pip install "kotaemon-app[slide]"
kotaemon app init
kotaemon app doctor
slide doctor
slide docqa --help
```

For a fresh environment, run `slide docqa doctor` before your first `slide docqa index`, `slide docqa files`, `slide docqa delete`, `slide docqa ask`, `slide docqa chat`, `slide docqa resume`, or `slide docqa sessions` command.

The same install also exposes the slide-specific `slide-docqa*` skill family under `.codex/skills`, including `slide-docqa-delete`.
`slide docqa acceptance` and `slide docqa check` remain available as maintainer workflows outside the focused DocQA mainline skill family.

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
