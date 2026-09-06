from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nd_mind_mirror.graphic.bridge.graphic_path_alias_registry import (
    GraphicPathAliasRegistry,
)
from nd_mind_mirror.graphic.core.bridge_path_notifier import GraphicBridgePathNotifier


def test_alias_registry_remaps_stale_file_and_chained_renames(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry = GraphicPathAliasRegistry(workspace)

    registry.register("project/img_4.ndgraphic", "project/agent_tree.ndgraphic")
    registry.register("project/agent_tree.ndgraphic", "project/final_tree.ndgraphic")

    assert registry.resolve("project/img_4.ndgraphic") == (
        workspace / "project/final_tree.ndgraphic"
    ).resolve(strict=False)



def test_alias_registry_handles_rename_back_to_an_old_name(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry = GraphicPathAliasRegistry(workspace)

    registry.register("paper/a.ndgraphic", "paper/b.ndgraphic")
    registry.register("paper/b.ndgraphic", "paper/a.ndgraphic")

    assert registry.resolve("paper/a.ndgraphic") == (
        workspace / "paper/a.ndgraphic"
    ).resolve(strict=False)
    assert registry.resolve("paper/b.ndgraphic") == (
        workspace / "paper/a.ndgraphic"
    ).resolve(strict=False)

def test_alias_registry_remaps_paths_under_renamed_folder(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry = GraphicPathAliasRegistry(workspace)

    registry.register("old_folder", "new_folder")

    assert registry.resolve("old_folder/a/image.ndgraphic") == (
        workspace / "new_folder/a/image.ndgraphic"
    ).resolve(strict=False)


def test_alias_registry_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    registry = GraphicPathAliasRegistry(workspace)

    outside = tmp_path / "outside.ndgraphic"
    try:
        registry.register(outside, workspace / "inside.ndgraphic")
    except ValueError:
        pass
    else:
        raise AssertionError("outside-workspace aliases must be rejected")


def test_path_notifier_persists_rename_before_http_nudge(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    notifier = GraphicBridgePathNotifier(workspace, bridge_http_url="")

    old = workspace / "paper/img_4.ndgraphic"
    new = workspace / "paper/agent_tree.ndgraphic"
    assert notifier.notify_rename(old, new)

    request_path = workspace / ".nd_mind_mirror/graphic_rename_request.json"
    deadline = time.monotonic() + 1.0
    while not request_path.is_file() and time.monotonic() < deadline:
        time.sleep(0.01)

    payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert payload["old_path"] == "paper/img_4.ndgraphic"
    assert payload["new_path"] == "paper/agent_tree.ndgraphic"
    assert int(payload["request_id"]) > 0
