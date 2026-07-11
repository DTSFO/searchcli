# Persistence and State Guidelines

## No database layer

The project currently uses no database, ORM, schema migrations, or durable
server-side records. Do not introduce database conventions or dependencies for
features that fit the existing in-memory/file-backed model.

## Persisted configuration

The only durable application state is the user's model preference in
`~/.config/grok-search/config.json`, managed by `Config` in `config.py`.

- Resolve configuration through `config` properties. The established precedence
  is explicit service environment variable, derived `GUDA_API_KEY` value where
  applicable, persisted model value, then project default.
- Read and write JSON as UTF-8. `Config._save_config_file` uses
  `ensure_ascii=False` and `indent=2`.
- Treat missing files and invalid JSON as an empty configuration, as implemented
  by `_load_config_file`.
- Raise a user-facing `ValueError` when a requested write cannot be completed.
- Keep secrets in environment variables. The JSON file currently stores only
  the model selection; do not persist API keys there.

## In-memory state

- Bounded caches use explicit synchronization because MCP tools are async.
  `SourcesCache` in `sources.py` protects its ordered dictionary with
  `asyncio.Lock` and evicts the least-recently-used item above `max_size`.
- Shared model discovery in `server.py` uses `_AVAILABLE_MODELS_LOCK` and keys
  entries by `(api_url, api_key)`.
- Search-planning sessions belong to `PlanningEngine` in `planning.py`; state
  transitions should remain in that domain object instead of being duplicated
  across the six MCP wrappers.

## When adding state

Prefer an existing owner:

- user preference -> `Config` and its JSON file;
- short-lived per-search data -> a bounded async cache;
- planning workflow state -> `PlanningEngine`;
- upstream response data -> normalize it into plain dictionaries at the
  boundary before caching or returning it.

Avoid unbounded module-level dictionaries, unsynchronized mutation from async
tools, plaintext secret persistence, and new durable storage without an explicit
requirement for lifecycle, compatibility, and migration behavior.

