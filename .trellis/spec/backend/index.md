# Backend Development Guidelines

This is a single-package Python FastMCP server. Read the guides that match the
code being changed.

## Guidelines index

| Guide | Use it for |
|---|---|
| [Directory Structure](./directory-structure.md) | Module ownership, imports, and placement |
| [Persistence and State](./database-guidelines.md) | Config files, caches, planning state, and the absence of a database |
| [Error Handling](./error-handling.md) | MCP errors, optional-provider fallback, and retries |
| [Logging](./logging-guidelines.md) | File/context logging and stdio safety |
| [Quality](./quality-guidelines.md) | Compatibility, verification, and review checks |

## Pre-development checklist

1. Read `directory-structure.md` for every backend change.
2. Read `error-handling.md` and `logging-guidelines.md` for provider, HTTP, or
   MCP boundary changes.
3. Read `database-guidelines.md` for config, cache, or planning-session state.
4. Read `quality-guidelines.md` before implementation and again before review.
5. Read the shared guides in `../guides/index.md`; search existing owners before
   creating helpers or changing cross-layer payloads.

All guides describe the current codebase. Update them when a deliberate
architecture or convention change lands.

