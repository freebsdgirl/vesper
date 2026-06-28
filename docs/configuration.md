# Configuration

Vesper loads runtime settings from a JSON config file plus environment-variable overrides.

## Config File Lookup Order

`Settings.from_env()` checks these locations in order and uses the first file that exists:

1. `VESPER_CONFIG_PATH`
2. `./config.json`
3. `$XDG_CONFIG_HOME/vesper/config.json`, or `~/.config/vesper/config.json` when `XDG_CONFIG_HOME` is unset

Unknown config keys are rejected so typos fail early.

Start from the example file. Installed as a tool:

```bash
vesper config init
```

This writes the packaged template to `~/.config/vesper/config.json` (use `--path` to choose a different location, `--force` to overwrite). In a clone you can also copy it directly:

```bash
cp vesper/config.example.json config.json
```

## Environment Overrides

Every configurable field has an environment variable override. Environment variables win over the JSON file.

| Config key | Environment variable | Default |
| --- | --- | --- |
| `http_host` | `VESPER_HTTP_HOST` | `127.0.0.1` |
| `http_port` | `VESPER_HTTP_PORT` | `8766` |
| `public_base_url` | `VESPER_PUBLIC_BASE_URL` | derived from host/port |
| `cider_base_url` | `VESPER_CIDER_BASE_URL` | `http://localhost:10767` |
| `cider_api_token` | `VESPER_CIDER_API_TOKEN` | `null` |
| `default_search_source` | `VESPER_DEFAULT_SEARCH_SOURCE` | `catalog` |
| `resolver_backend` | `VESPER_RESOLVER_BACKEND` | `fallback` |
| `resolver_base_url` | `VESPER_RESOLVER_BASE_URL` | `https://api.openai.com/v1` |
| `resolver_model` | `VESPER_RESOLVER_MODEL` | `null` |
| `resolver_api_key` | `VESPER_RESOLVER_API_KEY` | `null` |
| `resolver_include_reasoning` | `VESPER_RESOLVER_INCLUDE_REASONING` | `false` |
| `resolver_include_raw_output` | `VESPER_RESOLVER_INCLUDE_RAW_OUTPUT` | `false` |
| `resolver_debug_log_path` | `VESPER_RESOLVER_DEBUG_LOG_PATH` | `null` |
| `include_timing_debug` | `VESPER_INCLUDE_TIMING_DEBUG` | `false` |
| `response_detail` | `VESPER_RESPONSE_DETAIL` | `compact` |
| `session_recent_tracks_limit` | `VESPER_SESSION_RECENT_TRACKS_LIMIT` | `10` |
| `session_vibe_rephrase_attempts` | `VESPER_SESSION_VIBE_REPHRASE_ATTEMPTS` | `3` |
| `global_recent_tracks_limit` | `VESPER_GLOBAL_RECENT_TRACKS_LIMIT` | `10` |
| `request_timeout_seconds` | `VESPER_REQUEST_TIMEOUT_SECONDS` | `60.0` |
| `verify_tls` | `VESPER_VERIFY_TLS` | `true` |
| `log_level` | `VESPER_LOG_LEVEL` | `INFO` |
| `historian_enabled` | `VESPER_HISTORIAN_ENABLED` | `false` |
| `historian_base_url` | `VESPER_HISTORIAN_BASE_URL` | `http://127.0.0.1:8768` |
| `historian_token` | `VESPER_HISTORIAN_TOKEN` | `null` |
| `historian_timeout_seconds` | `VESPER_HISTORIAN_TIMEOUT_SECONDS` | `5.0` |
| `historian_verify_tls` | `VESPER_HISTORIAN_VERIFY_TLS` | `true` |
| `historian_retry_count` | `VESPER_HISTORIAN_RETRY_COUNT` | `2` |
| `database_path` | `VESPER_DATABASE_PATH` | `~/.local/share/vesper/vesper.db` |

Boolean values accept `1`, `true`, `yes`, `on`, `0`, `false`, `no`, `off`, and an empty string for false.

## Cider Settings

Set `cider_base_url` to the local Cider API endpoint. The default is:

```json
{
  "cider_base_url": "http://localhost:10767"
}
```

If your Cider build requires a token, set either:

```json
{
  "cider_api_token": "your-token-here"
}
```

or:

```bash
export VESPER_CIDER_API_TOKEN=your-token-here
```

## Resolver Settings

The resolver controls natural-language interpretation and adaptive-session choices.

### Fallback Resolver

```json
{
  "resolver_backend": "fallback"
}
```

The fallback resolver is deterministic and only handles simple direct commands. General requests such as `play upbeat morning music` need the OpenAI-compatible resolver.

### OpenAI-Compatible Resolver

```json
{
  "resolver_backend": "openai_compatible",
  "resolver_base_url": "https://api.openai.com/v1",
  "resolver_model": "gpt-4.1-mini",
  "resolver_api_key": "your-key"
}
```

Any compatible chat-completions endpoint can be used if it supports the response shape Vesper expects.

Useful debug options:

```json
{
  "resolver_debug_log_path": "/tmp/vesper-resolver.log",
  "resolver_include_reasoning": false,
  "resolver_include_raw_output": false
}
```

Keep raw output logging disabled unless you need it; resolver logs can contain request text, playback summaries, candidate tracks, and model responses. Saved preference rows are not included in the `resolve_text_request` or `plan_session_query` prompt context; preference-seeded sessions use those rows locally after the resolver chooses the abstract `preference` source.

## HTTP Settings

`http_host` and `http_port` control `vesper serve`. `public_base_url` is used in the A2A agent card and should be set to the URL other agents can reach.

```json
{
  "http_host": "127.0.0.1",
  "http_port": 8766,
  "public_base_url": "http://127.0.0.1:8766"
}
```

## Storage Settings

`database_path` controls the SQLite database used for music preferences and adaptive-session state.

```json
{
  "database_path": "~/.local/share/vesper/vesper.db"
}
```

The parent directory is created automatically.

## Historian Settings

Historian support is optional and disabled by default. When enabled, Vesper sends private playback, session, preference, and error events to Historian.

```json
{
  "historian_enabled": true,
  "historian_base_url": "http://127.0.0.1:8768",
  "historian_token": "token-from-historian"
}
```

Delivery failures are recorded/logged but do not make a successful music action fail.
