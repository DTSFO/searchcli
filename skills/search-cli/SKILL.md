---
name: search-cli
description: Use the local search CLI for real-time web search, source retrieval, page fetching, site mapping, model/config diagnostics, and persistent multi-phase search planning. Trigger when an agent needs current external information, citations, webpage content, site discovery, or a structured search plan through terminal commands.
---

# Search CLI

Use `search` as an Agent-facing command line tool. Its default output is JSON; parse the `ok`, `data`, `meta`, and `error` fields instead of scraping terminal prose.

## Start safely

1. Run `search --version` when compatibility matters.
2. Run `search config show` to inspect masked configuration. Use `--check` only when a live connection test is useful.
3. Never print, quote, log, or persist API keys. Do not inspect the managed credential file unless the user explicitly requests credential maintenance.
4. Read [references/command-contract.md](references/command-contract.md) when exact parameters, exit codes, or planning phases are needed.

## Choose the command

- Search the web: `search search "<query>"`
- Retrieve citations from a search response: `search sources get <session_id>`
- Fetch a page as Markdown: `search fetch <url>`
- Discover a site's URLs: `search map <url>`
- Inspect or switch models: `search model list|current|set`
- Build a structured plan for a complex research task: use the `search plan` phase commands below.

Use `--quiet` only when a scalar/body is sufficient. Use `--pretty` for human review. Do not combine them.

## Preserve search evidence

After `search`, retain `data.session_id`. Call `sources get` when citations, provenance, or source inspection matter. Check `meta.warnings` for `missing_citations` and `uncited_content`; never treat unresolved or uncited claims as supported. Sessions persist across processes for seven days.

## Run multi-phase planning

Call phases in this order:

1. `plan intent`
2. `plan complexity`
3. `plan sub-query` once per sub-query
4. `plan search-term` once per term when complexity requires it
5. `plan tool-mapping` once per mapping when complexity requires it
6. `plan execution` for level 3

Reuse the returned `session_id` and submit phases in order. Level 1 requires phases 1–3, level 2 requires phases 1–5, and level 3 requires all phases. Accumulative phases accept repeated calls, including multiple tool mappings for one sub-query. Singleton phases require `--revision`; revision invalidates downstream phases. Parallel groups cannot contain dependency pairs and execution IDs must be unique. Inspect `validation_errors` whenever `plan_complete` is false.

## Handle failures

Treat a nonzero exit status as failure and parse stderr's JSON envelope. Branch on `error.code`; do not infer failure from localized message text. Retry network/upstream errors only when appropriate. Fix configuration and usage errors instead of retrying unchanged commands.

Use `search session list|show|delete|clear` to inspect or clean persisted state. Do not edit state JSON directly.
