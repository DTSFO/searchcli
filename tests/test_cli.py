import json

from typer.testing import CliRunner

from grok_search.cli import app, package_version


runner = CliRunner()


def test_version_matches_package_metadata():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == package_version()


def test_model_current_is_json(monkeypatch, tmp_path):
    monkeypatch.setenv("GROK_MODEL", "test-model")
    result = runner.invoke(app, ["model", "current"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["model"] == "test-model"


def test_planning_cli_cross_process_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    result = runner.invoke(app, ["plan", "intent", "--thought", "t", "--core-question", "q", "--query-type", "factual", "--time-sensitivity", "recent"])
    assert result.exit_code == 0
    session_id = json.loads(result.stdout)["data"]["session_id"]
    result = runner.invoke(app, ["plan", "complexity", session_id, "--thought", "t", "--level", "1", "--estimated-sub-queries", "1", "--estimated-tool-calls", "1", "--justification", "simple"])
    assert result.exit_code == 0
    assert "complexity_assessment" in json.loads(result.stdout)["data"]["completed_phases"]
