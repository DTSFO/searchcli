# Command Contract

## Output

Success uses `{schema_version, ok: true, command, data, meta}`. Failure uses `{schema_version, ok: false, command, error: {code, message, details}}` on stderr.

Exit codes: `0` success, `1` internal, `2` usage, `3` configuration, `4` not found/expired, `5` network, `6` upstream service.

Invalid commands, missing/range-invalid options, blank queries, invalid URLs, and invalid planning payloads are usage errors. A bare `search` writes only a structured usage error to stderr. Search warnings may contain `missing_citations` or paragraph/sentence-level `uncited_content` for English and Chinese prose. Planning phases are ordered; singleton revisions invalidate downstream data, multiple tool calls may target one sub-query, execution IDs are unique, and dependency pairs cannot share a parallel group.

When `TAVILY_API_URL` comes from a Tavily Hikari MCP endpoint ending in `/mcp`, `search` automatically calls the same origin through `/api/tavily` for REST search, extract, and map operations.

## Core commands

Output flags are global. Use the canonical placement `search --pretty COMMAND ...` or `search --quiet COMMAND ...`. The CLI also accepts either flag at the very end for compatibility with tools that append options, but Agent instructions should always use the canonical placement.

```text
search search QUERY [--platform TEXT] [--model TEXT] [--extra-sources N]
search sources get SESSION_ID
search fetch URL
search map URL [--instructions TEXT] [--max-depth 1..5] [--max-breadth 1..500] [--limit 1..500] [--timeout 10..150]
search config show [--check]
search model list
search model current
search model set MODEL
search session list|show|delete|clear
```

## Planning commands

Inspect `search plan <phase> --help` for all scalar options. The stable phase names are:

```text
intent → complexity → sub-query → search-term → tool-mapping → execution
```

`intent` returns the `session_id`. Pass it as the positional argument to every later phase. Comma-separated options represent lists; `execution --parallel-groups` uses semicolons between parallel batches and commas inside a batch.

## Optional Claude integration

```text
search integrations claude status
search integrations claude disable-builtins
search integrations claude enable-builtins
```

These commands modify only `WebFetch` and `WebSearch` entries in the current Git project's `.claude/settings.json`.
