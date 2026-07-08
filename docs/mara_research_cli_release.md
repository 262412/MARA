# mara-research-cli Release Flow

`mara-research-cli` is published as its own Python package and shares the monorepo tag line with its internal runtime packages.

Phase 3 keeps the user-facing shell intentionally split into two lines:

- `MARA ...` is the high-permission product shell for runtime commands, app lifecycle, model routing, platform support, and workspace operations, including `MARA apply`, `MARA export-pdf`, and `MARA review`
- `MARA docqa ...` is the specialist document-QA line

The canonical top-level commands currently are:

- `MARA apply`
- `MARA app`
- `MARA export-pdf`
- `MARA model`
- `MARA platform`
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

`MARA inspect`, `MARA read-slide`, `MARA extract`, and `MARA search` are the canonical read-only deck-observability commands on the top-level line.

## Version Chain

- Package versions come from git tags through `setuptools-git-versioning`.
- Repository tags follow the `v0.0.x` pattern.
- A tag such as `v0.0.9` produces matching `0.0.9` builds for all Python packages in this repo.

## Publish Order

Release automation publishes packages in dependency order:

1. `ktem`
2. `kotaemon`
3. `mara-research-cli`
4. `mara-app`

This order is enforced by `scripts/publish_packages.py` and used by `.github/workflows/publish-packages.yaml`.

## Local Release Checks

Build and validate only `mara-research-cli`:

```shell
python scripts/publish_packages.py release --packages mara-research-cli --repository testpypi --skip-upload
```

Build and validate the full chain without uploading:

```shell
python scripts/publish_packages.py release --repository testpypi --skip-upload
```

## Packaged Runtime Workflow

The recommended MARA user path is to install the public CLI package, initialize the packaged runtime once, and then discover the canonical two-line shell from that environment:

```shell
pip install mara-research-cli
MARA app init
MARA app doctor
MARA --help
MARA doctor
MARA docqa --help
```

For a fresh environment, run `MARA doctor` first, then use `MARA docqa doctor` before your first `MARA docqa index`, `MARA docqa files`, `MARA docqa delete`, `MARA docqa ask`, `MARA docqa chat`, `MARA docqa resume`, or `MARA docqa sessions` command.

The same install also exposes the top-level `MARA*` skill family plus the specialist `MARA-docqa*` skill family under `.codex/skills`, including `MARA-docqa-delete`.
`MARA docqa acceptance` and `MARA docqa check` remain available as maintainer workflows outside the focused DocQA mainline skill family.

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
pip install mara-research-cli
MARA doctor
MARA --help
```

Or use TestPyPI:

```shell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mara-research-cli
```
