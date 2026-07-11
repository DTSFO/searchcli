from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OutputOptions:
    pretty: bool = False
    quiet: bool = False


def success(command: str, data: Any, meta: dict | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": command,
        "data": data,
        "meta": meta or {},
    }


def failure(command: str, code: str, message: str, details: dict | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "command": command,
        "error": {"code": code, "message": message, "details": details or {}},
    }


def render(payload: dict, options: OutputOptions, quiet_value: Any = None) -> str:
    if options.quiet:
        value = quiet_value if quiet_value is not None else payload.get("data", payload)
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if options.pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

