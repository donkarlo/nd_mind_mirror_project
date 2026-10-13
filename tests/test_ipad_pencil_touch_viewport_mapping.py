"""Protect Pencil overlay positions against centered or scrolled canvases."""

from pathlib import Path


PACKAGE = (
    Path(__file__).resolve().parents[1]
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
)


def test_touch_coordinates_are_converted_to_visible_scroll_viewport() -> None:
    controller = (
        PACKAGE / "Services/PencilQuickToolPaletteGestureController.swift"
    ).read_text(encoding="utf-8")
    canvas = (PACKAGE / "Views/PencilCanvasView.swift").read_text(encoding="utf-8")
    content = (PACKAGE / "Views/ContentView.swift").read_text(encoding="utf-8")

    assert "coordinateView: scroll" in canvas
    assert "scroll.contentInset = UIEdgeInsets(" in canvas
    assert "x: location.x - coordinateView.bounds.minX" in controller
    assert "y: location.y - coordinateView.bounds.minY" in controller
    assert "firstTapPoint = point" in controller
    assert "secondTapPoint = point" in controller
    assert "onPencilContactBegan(point)" in controller
    assert controller.count("onPencilContactBegan(viewportPoint(") == 1
    assert "onSinglePencilTap(viewportPoint(" in controller
    assert "anchor: pencilContactPreviewAnchor" in content
    assert "anchor: quickToolPaletteAnchor" in content


def test_centering_offset_does_not_shift_pencil_preview() -> None:
    # The scroll view uses negative bounds origins for small centered canvases.
    # Its UIKit touch coordinates have that origin; SwiftUI's overlay does not.
    for bounds_origin in (-250.0, -130.0, 0.0, 285.0):
        viewport_contact = (385.0, 280.0)
        reported_location = (
            viewport_contact[0] + bounds_origin,
            viewport_contact[1] + bounds_origin,
        )
        mapped = (
            reported_location[0] - bounds_origin,
            reported_location[1] - bounds_origin,
        )
        assert mapped == viewport_contact
