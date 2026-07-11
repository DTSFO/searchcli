from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .errors import ConfigAppError


CLAUDE_BUILTINS = ("WebFetch", "WebSearch")


def find_project_root(start: Path | None = None) -> Path:
    root = (start or Path.cwd()).resolve()
    for candidate in (root, *root.parents):
        if (candidate / ".git").exists():
            return candidate
    raise ConfigAppError("No Git project root found")


def claude_builtins(action: str, project_root: Path | None = None) -> dict:
    root = project_root.resolve() if project_root else find_project_root()
    path = root / ".claude" / "settings.json"
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigAppError(f"Unable to read valid Claude settings: {path}") from exc
    else:
        settings = {}
    deny = settings.setdefault("permissions", {}).setdefault("deny", [])
    if not isinstance(deny, list):
        raise ConfigAppError("Claude permissions.deny must be a list")
    if action == "disable":
        deny.extend(tool for tool in CLAUDE_BUILTINS if tool not in deny)
        _atomic_json(path, settings)
    elif action == "enable":
        deny[:] = [tool for tool in deny if tool not in CLAUDE_BUILTINS]
        _atomic_json(path, settings)
    blocked = all(tool in deny for tool in CLAUDE_BUILTINS)
    return {"blocked": blocked, "deny_list": deny, "file": str(path)}


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
