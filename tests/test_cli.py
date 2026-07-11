import json
import tomllib
import os
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from grok_search.cli import app, package_version


runner = CliRunner()


def test_version_matches_package_metadata():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == package_version()


def test_console_script_is_search_only():
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    scripts = project["project"]["scripts"]
    assert "search" in scripts
    assert "grok-search" not in scripts


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


def test_real_cli_usage_errors_are_structured(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src"), "XDG_STATE_HOME": str(tmp_path)}
    for args in (["bogus"], ["search"], ["map", "not-a-url"]):
        result = subprocess.run([sys.executable, "-m", "grok_search.cli", *args], env=env, text=True, capture_output=True)
        assert result.returncode == 2
        assert json.loads(result.stderr)["error"]["code"] == "usage_error"
