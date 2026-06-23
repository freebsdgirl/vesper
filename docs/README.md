# Vesper Documentation

This directory contains the developer and integration documentation for Vesper. The top-level README is user-focused; these files explain how the project works and where to change it.

## Start Here

- [Architecture](architecture.md) — the major components, request flow, persistence, and observability.
- [Adaptive Sessions, Search, and Preferences](adaptive-sessions.md) — how sessions differ from one-track playback, how typed search sources work, what preferences do, where the materialized session queue lives, and how steering/advancement behave.
- [Configuration](configuration.md) — config file lookup, environment variables, resolver settings, Cider, Historian, and storage.
- [Transports](transports.md) — CLI, A2A, and MCP entrypoints and how they map onto the service layer.
- [Development](development.md) — local setup, test commands, project layout, and change guidance.

## Core Idea

Vesper keeps the LLM-facing surface small. User and agent hosts can send plain-language music requests, while stateful behavior lives in Python code:

```text
CLI / A2A / MCP
      |
      v
CiderAgentService
      |
      +--> CiderRpcClient        # Cider HTTP/RPC calls
      +--> PreferenceStore       # SQLite preferences + session state
      +--> Resolver              # small grounded decisions
      +--> SessionEngine         # adaptive sessions + background worker
      +--> HistorianSink         # optional private event stream
```

That design keeps the main conversational agent from needing a large music schema and keeps smaller resolver models from needing to reason over large histories.
