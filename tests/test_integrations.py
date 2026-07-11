import json

from grok_search.integrations import claude_builtins


def test_claude_integration_preserves_unrelated_settings(tmp_path):
    (tmp_path / ".git").mkdir()
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"theme": "dark", "permissions": {"deny": ["Other"]}}), encoding="utf-8")
    disabled = claude_builtins("disable", tmp_path)
    assert disabled["blocked"] is True
    enabled = claude_builtins("enable", tmp_path)
    assert enabled["blocked"] is False
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["permissions"]["deny"] == ["Other"]

