# Command Contract

## Output

Success uses `{schema_version, ok: true, command, data, meta}`. Failure uses `{schema_version, ok: false, command, error: {code, message, details}}` on stderr.

Exit codes: `0` success, `1` internal, `2` usage, `3` configuration, `4` not found/expired, `5` network, `6` upstream service.

## Core commands

```text
grok-search search QUERY [--platform TEXT] [--model TEXT] [--extra-sources N]
grok-search sources get SESSION_ID
grok-search fetch URL
grok-search map URL [--instructions TEXT] [--max-depth 1..5] [--max-breadth 1..500] [--limit 1..500] [--timeout 10..150]
grok-search config show [--check]
grok-search model list
grok-search model current
grok-search model set MODEL
grok-search session list|show|delete|clear
```

## Planning commands

Inspect `grok-search plan <phase> --help` for all scalar options. The stable phase names are:

```text
intent → complexity → sub-query → search-term → tool-mapping → execution
```

`intent` returns the `session_id`. Pass it as the positional argument to every later phase. Comma-separated options represent lists; `execution --parallel-groups` uses semicolons between parallel batches and commas inside a batch.

## Optional Claude integration

```text
grok-search integrations claude status
grok-search integrations claude disable-builtins
grok-search integrations claude enable-builtins
```

These commands modify only `WebFetch` and `WebSearch` entries in the current Git project's `.claude/settings.json`.
