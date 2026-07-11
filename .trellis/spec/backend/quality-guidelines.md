# Quality Guidelines

## Compatibility baseline

- Support Python 3.10 and later as declared in `pyproject.toml`. Syntax such as
  `list[str]`, `str | None`, async functions, and type annotations is normal.
- Preserve both package execution and MCP launch compatibility. `server.py`
  intentionally contains a `src` path setup and absolute/relative import
  fallback.
- Keep MCP parameter schemas scalar and explicit. The planning API is split into
  six phase tools and converts comma-separated strings with `_split_csv` because
  downstream clients may not support nested Pydantic JSON Schema reliably.
- Preserve documented tool result dictionaries and session/source ordering.

## Local patterns to follow

- Use `Annotated[..., "description"]` and `pydantic.Field` constraints at MCP
  boundaries, as shown throughout `server.py`.
- Isolate external services in small async helpers/provider methods and use
  `httpx.AsyncClient` with explicit timeouts.
- Normalize and deduplicate at one boundary. `merge_sources` and
  `_normalize_sources` in `sources.py` preserve first-seen order while rejecting
  invalid URLs.
- Protect shared mutable async state with `asyncio.Lock`.
- Keep configuration precedence and secret masking in `Config`.
- Add docstrings where a helper's protocol or fallback is not obvious; concise
  Chinese docstrings/comments are established in the current source.

## Verification

There is currently no committed automated test suite or configured linter.
Before reporting a change complete, run at least:

```bash
python -m compileall -q src
python -c "from grok_search.server import mcp"
```

For behavior changes, add focused tests rather than relying only on imports.
The highest-value units are pure helpers in `sources.py`, phase accumulation in
`planning.py`, configuration precedence/masking in `config.py`, and retry/SSE
parsing in `providers/grok.py`. Network tests should mock HTTP responses and
must not require real credentials.

When dependencies or entry points change, also build the package if the build
tool is available and verify the console script still imports.

## Review checklist

- Does the change preserve Python 3.10 compatibility and the MCP tool contract?
- Are raw environment lookups, URL normalization, caching, or provider calls
  duplicated instead of using their existing owner?
- Can optional-provider failure degrade cleanly without hiding a required Grok
  failure?
- Are timeouts and retry classifications explicit for new network calls?
- Are secrets masked and stdout kept clean for stdio transport?
- Does shared async state have bounded growth and locking?
- Were README and `docs/README_EN.md` kept consistent for user-visible config or
  tool changes?

## Avoid

- Do not add nested request models to MCP tools without checking client schema
  compatibility.
- Do not use blocking HTTP/file work inside hot async paths when an async API is
  available.
- Do not depend on live Grok/Tavily/Firecrawl services in automated tests.
- Do not perform broad formatting or unrelated rewrites in `server.py`; it is a
  large integration module and small, reviewable changes are safer.

