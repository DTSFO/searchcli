import os

from grok_search.config import Config


def fresh_config(tmp_path, monkeypatch):
    instance = Config()
    instance._config_file = tmp_path / "config.json"
    instance._cached_model = None
    instance._env_loaded = False
    for name in ("GROK_API_URL", "GROK_API_KEY", "GROK_MODEL", "TAVILY_API_URL", "TAVILY_URL", "TAVILY_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return instance


def test_import_env_maps_tavily_alias_and_masks_keys(tmp_path, monkeypatch):
    source = tmp_path / "input.env"
    source.write_text("GROK_API_URL=https://example.test/v1\nGROK_API_KEY=secret-value\nTAVILY_URL=https://tavily.test\nTAVILY_API_KEY=other-secret\n", encoding="utf-8")
    settings = fresh_config(tmp_path / "config-home", monkeypatch)
    result = settings.import_env_file(source)
    assert "TAVILY_API_URL" in result["variables"]
    assert "TAVILY_URL" not in result["variables"]
    assert settings.tavily_api_url == "https://tavily.test"
    assert "secret-value" not in str(settings.get_config_info())
    assert settings.env_file.stat().st_mode & 0o777 == 0o600

