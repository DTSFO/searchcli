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

