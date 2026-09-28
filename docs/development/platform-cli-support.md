# MARA Platform CLI Support

The `MARA` CLI includes a `platform` command group for installing and validating
single-repo support bundles for external AI coding tools.

Here, platform means an AI coding-tool bundle, not an operating-system support
claim. Desktop OS/package support is recorded in the
[Desktop acceptance plan](../desktop/release-and-acceptance-plan.md).

Supported coding-tool bundles:

- `claude-code`
- `codex`

## Quick Start

```shell
# Show supported platforms and default target folders
MARA platform list

# Install a full Claude Code bundle to an explicitly owned target
MARA platform install --platform claude-code --mode full --target-dir ./tmp/claude --yes

# Install a minimal Codex bundle to a custom target
MARA platform install --platform codex --mode minimal --target-dir ./tmp/codex --yes

# Validate packaged bundle assets
MARA platform validate

# Validate one installed target
MARA platform validate --installed --platform codex --target-dir ./tmp/codex

# Inspect install status
MARA platform status --platform codex --target-dir ./tmp/codex
```

Omitting `--target-dir` writes the real user tool directory. Examples and tests
should use an owned target and fake settings. Existing primary instruction files
remain in place; bundle content uses the documented sidecar files below.

## Install Modes

- `full`: install all bundle components for the platform.
- `minimal`: install only the required baseline components.
- `selective`: install explicit components via repeated `--item`.

Example:

```shell
MARA platform install \
  --platform claude-code \
  --mode selective \
  --item skills \
  --item hooks \
  --target-dir ./tmp/claude \
  --yes
```

## Merge and Sidecar Rules

- Existing `CLAUDE.md` and `AGENTS.md` files are preserved; MARA content is written to
  `CLAUDE.slide.md` or `AGENTS.slide.md`.
- `settings.json.template` is copied to `settings.slide.template.json`, then merged into
  `settings.json`: missing dictionary keys and unique list entries are added;
  existing scalar values are preserved.
- `config.toml.template` is copied to `config.slide.template.toml`, then appended to
  `config.toml` unless the MARA marker block already exists.
- Existing files are backed up under `.slide-platform-backups/<timestamp>/`.

## CI Recommendation

Add this command to CI to ensure bundled assets remain complete:

```shell
MARA platform validate
```
