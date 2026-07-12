import os
import subprocess
import sys
from pathlib import Path


def test_public_modules_import_in_fresh_processes():
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    for module in ("grok_search.sources", "grok_search.utils", "grok_search.providers"):
        result = subprocess.run([sys.executable, "-c", f"import {module}"], env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr


def test_lazy_provider_export_is_backward_compatible():
    from grok_search.providers import GrokSearchProvider
    from grok_search.providers.grok import GrokSearchProvider as ConcreteProvider
    assert GrokSearchProvider is ConcreteProvider
