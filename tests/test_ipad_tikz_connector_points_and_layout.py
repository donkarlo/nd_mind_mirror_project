"""Regression checks for TikZ connection points and selectable auto-layout directions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_connection_points_default_to_four_and_live_on_shape_perimeter() -> None:
    metadata = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZConnectionPointMetadata.swift"
    )
    geometry = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Utilities/TikZ/TikZConnectionPointGeometry.swift"
    )
    overlay = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZConnectionPointOverlay.swift"
    )
    assert "defaultCount = 4" in metadata
    assert "rectanglePoints" in geometry
    assert "ellipsePoints" in geometry
    assert "perimeter" in geometry
    assert "cumulative" in geometry
    assert "TikZConnectionPointOverlay" in overlay


def test_connection_point_count_is_persisted_in_compile_safe_comments() -> None:
    metadata = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZConnectionPointMetadata.swift"
    )
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert "% nd-connection-points " in metadata
    assert "static func updating(" in metadata
    assert "static func removing(" in metadata
    assert "addConnectionPoint" in workspace
    assert "current + 1" in workspace


def test_auto_layout_exposes_all_six_requested_directions() -> None:
    direction = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Models/TikZ/TikZAutoLayoutDirection.swift"
    )
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    service = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZAutoLayoutService.swift"
    )
    for value in (
        "topToBottom",
        "bottomToTop",
        "leftToRight",
        "rightToLeft",
        "rightTree",
        "leftTree",
    ):
        assert value in direction
        assert value in service
    assert "ForEach(TikZAutoLayoutDirection.allCases)" in workspace


def test_blank_drop_can_create_target_shape_or_discard_connector() -> None:
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert ".confirmationDialog(" in workspace
    assert '"Connect to Rectangle"' in workspace
    assert '"Connect to Ellipse"' in workspace
    assert '"Delete Connector"' in workspace
    assert "TikZNodeNameAllocator" in workspace
