# Vesper

[![CI](https://github.com/randileeharper/vesper/actions/workflows/ci.yml/badge.svg)](https://github.com/randileeharper/vesper/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/tag/randileeharper/vesper?label=version)](https://github.com/randileeharper/vesper/tags)

`Vesper` is a dedicated music-control agent for the [Cider](https://cider.sh/) Apple Music client. It gives humans and agent hosts a small, text-first interface for playback control, adaptive music sessions, playlist requests, and music preference memory.

The project is built around one principle: keep the main conversational agent lean, and hand music work to a narrow specialist that knows how to talk to Cider.

## What Vesper Does

- Controls local Cider playback: play, pause, stop, next, previous, and status-like requests.
- Accepts natural-language music requests such as `play upbeat morning music` or `i don't like this`.
- Runs adaptive sessions for vague requests, selecting real Apple Music candidates instead of asking a model to invent tracks.
- Remembers explicit music preferences in SQLite.
- Exposes three entrypoints over the same service layer:
  - local CLI
  - A2A HTTP transport
  - MCP stdio or Streamable HTTP transport

## Requirements

- Python 3.12+
- uv (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Cider running locally
- Cider external application access enabled
- a Cider API token if your Cider build requires one

## Install

**For users (recommended):**

```bash
uv tool install git+https://github.com/randileeharper/vesper
vesper config init
```

This installs the `vesper` command and writes a default config to `~/.config/vesper/config.json`. Edit that file for your Cider token and resolver settings. See [docs/configuration.md](docs/configuration.md) for the full configuration reference.

**For developers:**

```bash
git clone https://github.com/randileeharper/vesper.git
cd vesper
uv sync --extra dev
cp vesper/config.example.json config.json   # or: vesper config init
```

See [docs/development.md](docs/development.md) for the local workflow.

### Updating

To update a tool install, reinstall to pull the latest:

```bash
uv tool install --force git+https://github.com/randileeharper/vesper
```

`uv tool upgrade vesper` does not work for git-based installs — it only upgrades tools installed by name from PyPI. To pin a specific release, install from a tag:

```bash
uv tool install git+https://github.com/randileeharper/vesper@v0.1.0
```

## Quick Start

CLI commands run directly against the local service. No HTTP server is required.

```bash
vesper play
vesper pause
vesper stop
vesper ask "play some music"
vesper ask "play something upbeat for the morning"
vesper ask "what playlists do I have?"
vesper ask "i don't like this"
vesper preferences list
```

Run HTTP transports when another process or agent host needs to connect:

```bash
# A2A HTTP
vesper serve --a2a

# MCP over stdio
vesper mcp

# MCP over Streamable HTTP
vesper serve --mcp

# A2A and MCP over one FastAPI app
vesper serve --a2a --mcp
```

## Recommended Integration Pattern

Use plain text first.

Most integrations should send requests like:

- `play upbeat morning music`
- `play some music`
- `more pop`
- `what's playing?`
- `play playlist Mix`
- `i like this track`
- `i don't like this`

Structured actions exist, but the public surface is intentionally tiny: `play`, `pause`, `stop`, `list_preferences`, and `forget_preference`. Richer behavior should go through natural-language text so Vesper can use its resolver, search, session, and preference machinery.

## Documentation

The README is only the front door. The deeper docs live in [`docs/`](docs/README.md):

- [Architecture](docs/architecture.md) explains the service, resolver, persistence, and event flow.
- [Adaptive Sessions, Search, and Preferences](docs/adaptive-sessions.md) explains preferences, typed search sources, sessions vs. one-track playback, the materialized session queue, steering, and track advancement.
- [Configuration](docs/configuration.md) covers config files, environment overrides, resolver settings, Cider, Historian, and storage.
- [Transports](docs/transports.md) documents CLI, A2A, and MCP behavior.
- [Development](docs/development.md) explains the local workflow, tests, and where common changes belong.

## Notes

- The public structured API is intentionally small; text is the main interface.
- Resolver prompts are intentionally compact so smaller local/open models can succeed.
- Playback state, preferences, session runtime, repeat avoidance, and output shaping live in code rather than prompt text.
- Historian event delivery is optional and never turns an otherwise successful music action into a failure.
