# Slide Platform CLI Support

The `slide` CLI includes a `platform` command group for installing and validating
single-repo support bundles for external AI coding tools.

Supported platforms:

- `claude-code`
- `codex`

## Quick Start

```shell
# Show supported platforms and default target folders
slide platform list

# Install a full Claude Code bundle to the default target (~/.claude)
slide platform install --platform claude-code --mode full --yes

# Install a minimal Codex bundle to a custom target
slide platform install --platform codex --mode minimal --target-dir ./tmp/codex --yes

# Validate packaged bundle assets
slide platform validate

# Validate one installed target
slide platform validate --installed --platform codex --target-dir ./tmp/codex

# Inspect install status
slide platform status --platform codex --target-dir ./tmp/codex
```

## Install Modes

- `full`: install all bundle components for the platform.
- `minimal`: install only the required baseline components.
- `selective`: install explicit components via repeated `--item`.

Example:

```shell
slide platform install \
  --platform claude-code \
  --mode selective \
  --item skills \
  --item hooks \
  --target-dir ./tmp/claude \
  --yes
```

## Merge and Sidecar Rules

- Existing `CLAUDE.md` and `AGENTS.md` files are preserved; slide content is written to
  `CLAUDE.slide.md` or `AGENTS.slide.md`.
- `settings.json.template` is copied to `settings.slide.template.json`, then merged into
  `settings.json` by adding missing keys only.
- `config.toml.template` is copied to `config.slide.template.toml`, then appended to
  `config.toml` unless the slide marker block already exists.
- Existing files are backed up under `.slide-platform-backups/<timestamp>/`.

## CI Recommendation

Add this command to CI to ensure bundled assets remain complete:

```shell
slide platform validate
```
