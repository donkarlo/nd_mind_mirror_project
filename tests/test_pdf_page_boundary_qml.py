from pathlib import Path


def test_pdf_page_boundary_uses_rendered_page_geometry() -> None:
    project_root = Path(__file__).resolve().parents[1]
    qml_path = project_root / "src" / "nd_mind_mirror" / "ui" / "preview" / "pdf" / "selectable_pdf_view.qml"
    source = qml_path.read_text(encoding="utf-8")

    assert "SelectablePdfViewBase" in source
    assert "function currentPageScrollBounds()" in source
    assert "paper.mapToItem" in source
    assert "function clampToCurrentPage()" in source
    assert "function setExplicitHorizontalPosition(position)" in source
    assert "function setExplicitVerticalPosition(position)" in source
    assert "bounds.minimumX" in source
    assert "bounds.maximumX" in source
    assert "bounds.minimumY" in source
    assert "bounds.maximumY" in source
