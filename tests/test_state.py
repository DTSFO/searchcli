from datetime import datetime, timedelta, timezone

import pytest

from grok_search.errors import NotFoundAppError
from grok_search.state import StateRepository


def test_state_round_trip_across_instances(tmp_path):
    repo = StateRepository(tmp_path)
    repo.save("sources", "abc123", [{"url": "https://example.com"}])
    loaded = StateRepository(tmp_path).load("sources", "abc123")
    assert loaded["data"] == [{"url": "https://example.com"}]
    assert (tmp_path / "sources" / "abc123.json").stat().st_mode & 0o777 == 0o600


def test_expired_state_is_removed(tmp_path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo = StateRepository(tmp_path, clock=lambda: now, ttl=timedelta(seconds=1))
    repo.save("planning", "expired", {"value": 1})
    expired_repo = StateRepository(tmp_path, clock=lambda: now + timedelta(seconds=2))
    with pytest.raises(NotFoundAppError):
        expired_repo.load("planning", "expired")
    assert not (tmp_path / "planning" / "expired.json").exists()


def test_read_without_refresh_preserves_timestamps(tmp_path):
    times = iter([
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    ])
    repo = StateRepository(tmp_path, clock=lambda: next(times))
    saved = repo.save("planning", "readonly", {"value": 1})
    loaded = repo.load("planning", "readonly", refresh=False)
    assert loaded == saved


def test_lock_inode_is_stable_across_delete_and_reuse(tmp_path):
    repo = StateRepository(tmp_path)
    repo.save("planning", "reused", {"value": 1})
    with repo.lock("planning", "reused"):
        pass
    lock_path = tmp_path / "planning" / "reused.lock"
    inode = lock_path.stat().st_ino
    assert repo.delete("planning", "reused") is True
    assert lock_path.exists()
    with repo.lock("planning", "reused"):
        repo.save("planning", "reused", {"value": 2})
    assert lock_path.stat().st_ino == inode
    assert repo.load("planning", "reused", refresh=False)["data"] == {"value": 2}
