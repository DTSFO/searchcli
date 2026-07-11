# Directory Structure

## Project shape

This repository is a single Python package installed from `src/` and exposed as a
FastMCP stdio application. Runtime code lives under `src/grok_search/`; user-facing
setup and environment documentation lives in `README.md` and `docs/README_EN.md`.

```text
src/grok_search/
├── __init__.py          # exports the FastMCP application
├── server.py            # MCP tool boundaries and external-service orchestration
├── config.py            # environment/file configuration and defaults
├── logger.py            # package logger and Context logging bridge
├── planning.py          # stateful search-planning domain logic
├── sources.py           # source parsing, normalization, merging, and cache
├── utils.py             # URL/result formatting and prompt constants
└── providers/
    ├── base.py          # provider interface and SearchResult value object
    └── grok.py          # Grok HTTP/SSE adapter and retry behavior
```

`pyproject.toml` is the source of truth for packaging, dependencies, Python
version (`>=3.10`), and the `grok-search = grok_search.server:main` entry point.

## Module ownership

- Put MCP-decorated entry points and coordination across providers in
  `server.py`. Examples: `web_search`, `get_sources`, and the six planning tools.
- Put service-specific HTTP payloads, response parsing, and retry policy in a
  provider module. `providers/grok.py` owns `/chat/completions`, SSE parsing,
  `Retry-After`, and Grok-specific prompts.
- Put reusable source-contract logic in `sources.py`. `SourcesCache`,
  `split_answer_and_sources`, and `merge_sources` are used without FastMCP
  knowledge.
- Put environment and persisted user preferences behind the singleton `config`
  in `config.py`; callers should not duplicate `os.getenv` precedence rules.
- Keep long prompt text and small presentation helpers in `utils.py`, rather
  than expanding already-large MCP handlers.

## Naming and imports

- Modules and functions use `snake_case`; classes use `PascalCase`; module-level
  constants use `UPPER_SNAKE_CASE`.
- Internal-only helpers start with `_`, as in `_fetch_available_models`,
  `_safe_tavily`, and `_parse_sources_payload`.
- Package modules use relative imports. `server.py` deliberately supports both
  absolute and relative imports because it is run by multiple MCP launch modes;
  preserve that compatibility block when changing imports there.
- New providers implement `BaseSearchProvider` and are exported from
  `providers/__init__.py` when they are part of the public package surface.

## Avoid

- Do not put provider-specific HTTP details in `utils.py` or `sources.py`.
- Do not read environment variables independently in tool handlers when the
  value belongs to `Config`.
- Do not add another top-level package for a small helper; place it beside the
  domain owner until a real package boundary emerges.
- Do not remove the `src/` path/import compatibility in `server.py` without
  checking both the console entry point and direct `mcp run` usage.

