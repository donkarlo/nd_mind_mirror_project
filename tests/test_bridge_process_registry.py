from types import SimpleNamespace
from unittest.mock import patch

from nd_mind_mirror.graphic.core.bridge_process_registry import (
    GraphicBridgeProcessRegistry,
)


def test_bridge_pids_select_only_mind_mirror_bridge_processes():
    output = """
  101 /usr/bin/python other.py
  202 /home/u/venv/bin/python -m nd_mind_mirror.graphic.bridge --workspace /repo
  303 /home/u/venv/bin/python -m nd_mind_mirror.graphic.bridge --workspace /repo --host 0.0.0.0
"""
    completed = SimpleNamespace(stdout=output)
    with patch("subprocess.run", return_value=completed), patch("os.getpid", return_value=999):
        assert GraphicBridgeProcessRegistry().bridge_pids() == (202, 303)


def test_bridge_pids_excludes_current_process():
    output = "  202 /home/u/venv/bin/python -m nd_mind_mirror.graphic.bridge\n"
    completed = SimpleNamespace(stdout=output)
    with patch("subprocess.run", return_value=completed), patch("os.getpid", return_value=202):
        assert GraphicBridgeProcessRegistry().bridge_pids() == ()
