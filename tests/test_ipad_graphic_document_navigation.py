from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"


def test_image_header_exposes_back_and_forward_navigation() -> None:
    content = (PACKAGE / "Views/ContentView.swift").read_text(encoding="utf-8")

    assert 'Image(systemName: "chevron.left")' in content
    assert 'Image(systemName: "chevron.right")' in content
    assert ".disabled(!documentNavigation.canGoBack)" in content
    assert ".disabled(!documentNavigation.canGoForward)" in content
    assert "bridge.requestOpen(path: path)" in content


def test_navigation_history_owns_browser_style_branching() -> None:
    history = (
        PACKAGE / "Services/GraphicDocumentNavigationHistory.swift"
    ).read_text(encoding="utf-8")

    assert "final class GraphicDocumentNavigationHistory" in history
    assert "paths.removeSubrange((currentIndex + 1)..<paths.count)" in history
    assert "func backPath() -> String?" in history
    assert "func forwardPath() -> String?" in history
    assert "func remapPath(from oldPath: String, to newPath: String)" in history
