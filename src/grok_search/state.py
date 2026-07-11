from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .errors import NotFoundAppError


SCHEMA_VERSION = 1
DEFAULT_TTL = timedelta(days=7)
StateClock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_state_root() -> Path:
    xdg = os.getenv("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "grok-search"
    return Path.home() / ".local" / "state" / "grok-search"


class StateRepository:
    def __init__(self, root: Path | None = None, clock: StateClock = utc_now, ttl: timedelta = DEFAULT_TTL):
        self.root = root or default_state_root()
        self.clock = clock
        self.ttl = ttl

    def _dir(self, kind: str) -> Path:
        if kind not in {"planning", "sources"}:
            raise ValueError(f"Unknown state kind: {kind}")
        return self.root / kind

    def _path(self, kind: str, session_id: str) -> Path:
        safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
        if not safe_id or safe_id != session_id:
            raise NotFoundAppError(f"Invalid session id: {session_id}")
        return self._dir(kind) / f"{safe_id}.json"

    def save(self, kind: str, session_id: str, data: dict | list) -> dict:
        now = self.clock()
        path = self._path(kind, session_id)
        created_at = now
        if path.exists():
            try:
                created_at = datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["created_at"])
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                created_at = now
        record = {
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": (now + self.ttl).isoformat(),
            "data": data,
        }
        self._atomic_write(path, record)
        return record

    def load(self, kind: str, session_id: str, refresh: bool = True) -> dict:
        path = self._path(kind, session_id)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            self._validate(record, kind, session_id)
        except FileNotFoundError as exc:
            raise NotFoundAppError(f"Session '{session_id}' not found", {"kind": kind}) from exc
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise NotFoundAppError(f"Session '{session_id}' is invalid", {"kind": kind}) from exc
        if datetime.fromisoformat(record["expires_at"]) <= self.clock():
            path.unlink(missing_ok=True)
            raise NotFoundAppError(f"Session '{session_id}' expired", {"kind": kind})
        if refresh:
            record = self.save(kind, session_id, record["data"])
        return record

    def list(self, kind: str | None = None) -> list[dict]:
        kinds = [kind] if kind else ["planning", "sources"]
        records: list[dict] = []
        for item_kind in kinds:
            directory = self._dir(item_kind)
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                try:
                    record = self.load(item_kind, path.stem, refresh=False)
                    records.append({k: record[k] for k in ("kind", "session_id", "created_at", "updated_at", "expires_at")})
                except NotFoundAppError:
                    path.unlink(missing_ok=True)
        return sorted(records, key=lambda item: item["updated_at"], reverse=True)

    def delete(self, kind: str, session_id: str) -> bool:
        path = self._path(kind, session_id)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    def clear(self, kind: str | None = None) -> int:
        records = self.list(kind)
        count = 0
        for record in records:
            count += int(self.delete(record["kind"], record["session_id"]))
        return count

    @staticmethod
    def _validate(record: dict, kind: str, session_id: str) -> None:
        if record.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported state schema")
        if record.get("kind") != kind or record.get("session_id") != session_id:
            raise ValueError("State identity mismatch")
        if "data" not in record or "expires_at" not in record:
            raise ValueError("Incomplete state record")

    @staticmethod
    def _atomic_write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
