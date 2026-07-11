# Logging Guidelines

## Logger setup

Use the package logger defined in `logger.py`; do not configure independent
handlers in feature modules. It writes UTF-8 daily files named
`grok_search_YYYYMMDD.log` using:

```text
YYYY-MM-DD HH:MM:SS - grok_search - LEVEL - message
```

The level comes from `GROK_LOG_LEVEL` and defaults to `INFO`. Log-directory
selection is centralized in `Config.log_dir`, with home, working-directory, and
`/tmp` fallbacks. If file logging cannot initialize, the package installs a
`NullHandler` so startup still succeeds.

## MCP context logging

Call `await log_info(ctx, message, is_debug)` when a function may have a FastMCP
`Context`. The helper has two distinct behaviors:

- write to the file logger only when `is_debug` is true;
- forward the message to `ctx.info` whenever a context is present.

This pattern is used by `GrokSearchProvider.search` and streaming response
parsing. Keep the helper async and await it.

## Content and secrecy

- Log operational details useful for diagnosing provider requests and response
  parsing only when debug logging is enabled.
- Never log authorization headers or raw API keys. `Config.get_config_info`
  demonstrates the required masking via `_mask_api_key`.
- Treat full queries, fetched pages, and model responses as potentially
  sensitive. Existing debug messages can include queries/content; do not add
  equivalent production-level logging.
- Prefer concise event messages. Do not print to stdout/stderr from the MCP
  server because stdio is the protocol transport and extra output can corrupt
  clients.

## Avoid

- Do not call `logging.basicConfig()` in package modules.
- Do not add a console handler to the stdio server.
- Do not create log directories outside `Config.log_dir`.
- Do not claim structured JSON logging: the current project uses a stable plain
  text formatter.

