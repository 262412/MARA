# Platform CLI Support

The `kotaemon` CLI now includes a `platform` command group for installing and validating
single-repo support bundles for external AI coding tools.

Supported platforms:

- `claude-code`
- `codex`

## Quick Start

```shell
# Show supported platforms and default target folders
kotaemon platform list

# Install a full Claude Code bundle to the default target (~/.claude)
kotaemon platform install --platform claude-code --mode full --yes

# Install a minimal Codex bundle to a custom target
kotaemon platform install --platform codex --mode minimal --target-dir ./tmp/codex --yes

# Validate packaged bundle assets
kotaemon platform validate

# Validate one installed target
kotaemon platform validate --installed --platform codex --target-dir ./tmp/codex

# Inspect install status
kotaemon platform status --platform codex --target-dir ./tmp/codex
```

## Install Modes

- `full`: install all bundle components for the platform.
- `minimal`: install only the required baseline components.
- `selective`: install explicit components via repeated `--item`.

Example:

```shell
kotaemon platform install \
  --platform claude-code \
  --mode selective \
  --item skills \
  --item hooks \
  --target-dir ./tmp/claude \
  --yes
```

## Merge and Sidecar Rules

- Existing `CLAUDE.md` and `AGENTS.md` files are preserved; kotaemon content is written to
  `CLAUDE.kotaemon.md` or `AGENTS.kotaemon.md`.
- `settings.json.template` is copied to `settings.kotaemon.template.json`, then merged into
  `settings.json` by adding missing keys only.
- `config.toml.template` is copied to `config.kotaemon.template.toml`, then appended to
  `config.toml` unless the kotaemon marker block already exists.
- Existing files are backed up under `.kotaemon-platform-backups/<timestamp>/`.

## CI Recommendation

Add this command to CI to ensure bundled assets remain complete:

```shell
kotaemon platform validate
```
