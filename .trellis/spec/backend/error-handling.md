# Error Handling

## Boundary behavior

The project distinguishes between errors that should become stable MCP results
and errors that should propagate from the provider layer.

- Configuration failures are `ValueError`s raised by `Config` properties. MCP
  tools catch them at the boundary and return a normal result with a Chinese
  `配置错误` message. See `web_search` in `server.py`.
- Optional Tavily and Firecrawl calls are best-effort. `_call_tavily_search`,
  `_call_firecrawl_search`, and related helpers catch external failures and
  return `None`; the main Grok result can still succeed.
- The Grok adapter calls `response.raise_for_status()` and retries only known
  transient failures through `_is_retryable_exception` and `AsyncRetrying` in
  `providers/grok.py`. Non-retryable failures propagate to the caller.
- Parsing helpers return empty values or `None` for unrecognized optional
  formats. For example, malformed source payloads fall through to other parsing
  strategies in `sources.py`.

## Retry rules

Retry network errors, timeouts, remote protocol errors, and HTTP 408/429/5xx
statuses listed in `RETRYABLE_STATUS_CODES`. Honor numeric or HTTP-date
`Retry-After` values for 429 responses; otherwise use randomized exponential
backoff configured by `GROK_RETRY_*` variables.

Do not retry authentication, validation, or other deterministic 4xx errors.
Keep retry policy in the provider adapter, not in every MCP tool.

## User-facing result contracts

- Preserve each tool's documented dictionary shape on failure. `get_sources`
  returns an empty `sources` list plus `error="session_id_not_found_or_expired"`.
- Clear/cache the matching empty state when returning an early search error so a
  generated `session_id` never points to stale data.
- Validate optional model overrides against the available-model response when
  that response is available; return `无效模型` without issuing the search.
- Use empty string/list/`None` only where the caller explicitly treats that value
  as “optional provider unavailable.” Do not silently swallow required-path
  failures.

## Avoid

- Do not use a broad `except Exception` around an entire MCP handler. Broad
  catches are currently limited to optional provider isolation, model-list
  fallback, or deliberately tolerant parsers.
- Do not expose API keys, authorization headers, or raw configuration objects in
  error messages.
- Do not add retries around non-idempotent operations without defining duplicate
  request behavior.
- Do not change an established output schema by raising where callers currently
  receive a structured error dictionary.

