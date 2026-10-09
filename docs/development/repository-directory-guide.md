# Hidden directories and repository hygiene

A leading dot is a naming convention. Decide whether a directory belongs in Git
from its contents and consumers, not from its name.

## Shared directories to keep

| Directory    | Purpose                                                                         |
| ------------ | ------------------------------------------------------------------------------- |
| `.git/`      | Git history, branches, index, and worktree metadata. Managed by Git.            |
| `.github/`   | CI, release/security workflows, issue templates, and the pull-request template. |
| `.githooks/` | Repository hooks, including the worktree environment safeguard.                 |
| `.codex/`    | MARA project instructions, skills, profiles, and support helpers used by Codex. |

The installable platform bundles also live under
`libs/kotaemon/kotaemon/platform_support/assets/`. Those packaged assets serve
installed users; the repository-level `.codex` serves work in this checkout.
Both have a purpose. Validate the bundles with `MARA platform validate`.

An `.agents/` directory may contain useful agent skills; inspect its consumers
before changing it.

## Local directories that do not belong in Git

| Directory                                                        | Treatment                                                                                            |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `.idea/`                                                         | Personal JetBrains project state; ignored. Recreate through the IDE if needed.                       |
| `.vscode/`                                                       | Local editor preferences; ignored. Shared setup instructions belong in documentation.                |
| `.playwright-cli/`                                               | Temporary browser snapshots; ignored. Deliberate documentation screenshots belong in `docs/images/`. |
| `.superpowers/`                                                  | Working-session scratch state; ignored. Maintain durable guidance in existing docs.                  |
| `.tmp_publish_check/`                                            | Disposable package-validation builds; ignored.                                                       |
| `.hypothesis/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` | Regenerable test/tool caches; ignored. They can reappear when those tools run.                       |

Ignore rules and tooling exclusions allow these local directories to reappear.
Their contents are not required product inputs. Removed tracked material remains
recoverable from Git history.

## Runtime state needs a different decision

`.venv/` is a Python environment, and `.theflow/` can contain state from earlier
runtime versions. Neither should be deleted just because it is hidden. The
current source settings put TheFlow storage under the runtime cache directory,
but an old directory may still contain useful local state.

Likewise, preserve `.env`, application databases, indexes, uploaded documents,
and runtime directories such as `ktem_app_data/` unless their removal is
specifically intended. Back up complete runtime data before changing its layout.

Follow the [storage layout contract](storage-layout-contract.md) for canonical
environments and the maintainers' HPC deployment.

## Checking future additions

```shell
git status --short
git ls-files .codex .github .githooks
git ls-files .idea .vscode .playwright-cli .superpowers .tmp_publish_check
git check-ignore .idea/workspace.xml .vscode/settings.json .playwright-cli/example.yml .tmp_publish_check/example.whl
```

The third command should produce no tracked files.
Ignore rules do not remove files that are already tracked; removing those
requires an explicit reviewed Git change.
