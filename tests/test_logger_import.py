import json
import os
import subprocess
import sys
import site
from pathlib import Path


def test_imports_do_not_create_log_files(tmp_path):
    log_dir = tmp_path / "logs"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(Path(__file__).parents[1] / "src"), site.getusersitepackages()]), "HOME": str(tmp_path), "GROK_LOG_DIR": str(log_dir)}
    code = """
import logging
import grok_search.cli
import grok_search.logger as package_logger
import grok_search.providers.grok
import grok_search.services
print(sum(isinstance(h, logging.FileHandler) for h in package_logger.logger.handlers))
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"
    assert not log_dir.exists()


def test_debug_logging_initializes_one_file_handler(tmp_path):
    log_dir = tmp_path / "logs"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(Path(__file__).parents[1] / "src"), site.getusersitepackages()]), "HOME": str(tmp_path), "GROK_LOG_DIR": str(log_dir)}
    code = """
import asyncio, json, logging
from grok_search.logger import log_info, logger
asyncio.run(log_info(None, 'first', True))
asyncio.run(log_info(None, 'second', True))
print(json.dumps({'handlers': sum(isinstance(h, logging.FileHandler) for h in logger.handlers)}))
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["handlers"] == 1
    assert len(list(log_dir.glob("*.log"))) == 1
