# Grok Search CLI

An Agent-friendly CLI for real-time web search, page extraction, site mapping, source retrieval, and persistent multi-phase research planning. It uses Grok for AI search and Tavily/Firecrawl for content operations.

This release is CLI-only. The MCP server, FastMCP dependency, and MCP installation flow have been removed.

## Install

Python 3.10+ is required.

```bash
uvx --from git+https://github.com/GuDaStudio/GrokSearch@grok-with-tavily search --help

# local development
python -m pip install -e .
search --version
```

## Configure

Export variables directly:

```bash
export GROK_API_URL="https://your-api.example/v1"
export GROK_API_KEY="your-key"
export GROK_MODEL="grok-4.20-beta"
export TAVILY_API_URL="https://api.tavily.com"
export TAVILY_API_KEY="your-tavily-key"
```

GuDa users may configure only `GUDA_API_KEY`. You may also import an env-style file; `TAVILY_URL` is normalized to `TAVILY_API_URL`. A Tavily Hikari MCP endpoint such as `https://<origin>/mcp` is automatically converted to its REST-compatible base `https://<origin>/api/tavily`:

```bash
search config import-env /path/to/credentials.env
search config show --check
```

The managed credential file is user-readable only. Keys are never stored in search/planning sessions and are masked in diagnostics.

## Output

Compact JSON is the default. `--pretty` emits indented JSON and `--quiet` emits only the core value. They are global options, so the canonical placement is before the subcommand, for example `search --pretty model current` or `search --quiet fetch https://example.com`. For compatibility with Agents that append options, the CLI also accepts either flag at the very end. Output shape never changes based on TTY detection. Results use stdout; structured failures use stderr.

Exit codes: `0` success, `1` internal, `2` usage, `3` configuration, `4` not found/expired, `5` network, `6` upstream.

## Commands

```bash
search search "latest Python release" --extra-sources 3
search sources get SESSION_ID
search fetch https://example.com
search map https://docs.example.com --max-depth 2 --limit 100
search config show --check
search model list
search model current
search model set MODEL_ID
search session list
search session show SESSION_ID --kind planning
```

Use `search COMMAND --help` for the full scalar argument contract.

## Agent planning protocol

The stable order is:

```text
intent → complexity → sub-query → search-term → tool-mapping → execution
```

`plan intent` returns a persistent `session_id`. Submit phases in order and reuse that ID. Level 1 requires phases 1–3, level 2 phases 1–5, and level 3 all phases. Accumulative phases may be called repeatedly and one sub-query may have multiple tool calls; singleton phases require `--revision`, which invalidates downstream phases. `plan_complete` additionally requires unique execution IDs and forbids dependencies within one parallel group.

If an answer contains `[[N]]` citations that cannot be mapped to returned sources, `meta.warnings` reports `missing_citations`. Paragraph- and sentence-level checks report `uncited_content` for substantial uncited English or Chinese prose even when another paragraph is cited. The CLI never invents sources and normalizes equivalent URLs, including root slash variants. `session show` is strictly read-only.

## Claude Code integration

```bash
search integrations claude status
search integrations claude disable-builtins
search integrations claude enable-builtins
```

Only `WebFetch` and `WebSearch` entries in the current Git project's `.claude/settings.json` are managed.

## Agent Skill

The canonical Skill lives at `skills/search-cli` and can be installed at:

```text
~/.codex/skills/search-cli
~/.claude/skills/search-cli
~/.pi/agent/skills/search-cli
```

## MCP migration

Use `search`, `sources get`, `fetch`, `map`, `config show`, `model set`, the Claude integration commands, and the six `plan` subcommands in place of the former MCP tools. Remove old `claude mcp` configuration; this package no longer starts a stdio server.

## Development

```bash
python -m pip install -e '.[dev]'
python -m compileall -q src tests
python -m pytest -q
python -m build
```

[中文文档](../README.md) · MIT License
