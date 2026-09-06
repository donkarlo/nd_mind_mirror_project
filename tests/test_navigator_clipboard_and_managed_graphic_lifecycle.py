"""Regression checks for Navigator clipboard ownership and managed graphic lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

from nd_mind_mirror.core.workspace.operation.filesystem_operation_service import (
    WorkspaceFilesystemOperationService,
)
from nd_mind_mirror.graphic.core.sidecar_replacement_policy import (
    ManagedGraphicSidecarReplacementPolicy,
)


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_INTERACTION = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/workspace_interaction_controller.py"
).read_text(encoding="utf-8")
ENHANCED_WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")
MANAGED_CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/workspace/managed_graphic_filesystem_operation_controller.py"
).read_text(encoding="utf-8")


def test_workspace_interaction_keeps_multi_path_context_menu_owner() -> None:
    assert "self._context_controller.show_menu" in WORKSPACE_INTERACTION
    assert "def _show_navigator_menu" not in WORKSPACE_INTERACTION


def test_enhanced_window_has_no_duplicate_clipboard_ownership_controller() -> None:
    assert "NavigatorMultiPathOwnershipController" not in ENHANCED_WINDOW
    assert "NavigatorClipboardShortcutController" not in ENHANCED_WINDOW
    assert "NavigatorMultiPathContextController.replace(" in ENHANCED_WINDOW


def test_managed_raster_delete_includes_existing_sidecar() -> None:
    assert "def request_deletions" in MANAGED_CONTROLLER
    assert 'sidecar = path.with_suffix(".ndgraphic")' in MANAGED_CONTROLLER
    assert "super().request_deletions(expanded)" in MANAGED_CONTROLLER


def test_orphan_sidecar_can_be_replaced_for_same_owner(tmp_path: Path) -> None:
    source = tmp_path / "img_4.ndgraphic"
    destination = tmp_path / "agent_anatonomical_tree.ndgraphic"
    source.write_text(
        json.dumps(
            {
                "image_name": "img_4.png",
                "source_name": "neural_cognitive_architecture.tex",
            }
        ),
        encoding="utf-8",
    )
    destination.write_text(
        json.dumps(
            {
                "image_name": "agent_anatonomical_tree.png",
                "source_name": "neural_cognitive_architecture.tex",
            }
        ),
        encoding="utf-8",
    )

    assert ManagedGraphicSidecarReplacementPolicy.can_replace(source, destination)


def test_orphan_sidecar_replacement_is_rejected_when_raster_still_exists(
    tmp_path: Path,
) -> None:
    source = tmp_path / "img_4.ndgraphic"
    destination = tmp_path / "agent_anatonomical_tree.ndgraphic"
    source.write_text(
        json.dumps({"image_name": "img_4.png", "source_name": "owner.tex"}),
        encoding="utf-8",
    )
    destination.write_text(
        json.dumps(
            {
                "image_name": "agent_anatonomical_tree.png",
                "source_name": "owner.tex",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "agent_anatonomical_tree.png").write_bytes(b"existing")

    assert not ManagedGraphicSidecarReplacementPolicy.can_replace(source, destination)


def test_move_batch_remembers_orphan_replaceability_before_raster_move(
    tmp_path: Path,
) -> None:
    source_image = tmp_path / "img_4.png"
    source_sidecar = tmp_path / "img_4.ndgraphic"
    destination_image = tmp_path / "agent_anatonomical_tree.png"
    destination_sidecar = tmp_path / "agent_anatonomical_tree.ndgraphic"

    source_image.write_bytes(b"new-image")
    source_sidecar.write_text(
        json.dumps({"image_name": "img_4.png", "source_name": "owner.tex"}),
        encoding="utf-8",
    )
    destination_sidecar.write_text(
        json.dumps(
            {
                "image_name": "agent_anatonomical_tree.png",
                "source_name": "owner.tex",
            }
        ),
        encoding="utf-8",
    )

    result = WorkspaceFilesystemOperationService().execute(
        {
            "moves": [
                {"source": str(source_image), "destination": str(destination_image)},
                {"source": str(source_sidecar), "destination": str(destination_sidecar)},
            ]
        }
    )

    assert [item["success"] for item in result["moves"]] == [True, True]
    assert destination_image.read_bytes() == b"new-image"
    assert destination_sidecar.is_file()
