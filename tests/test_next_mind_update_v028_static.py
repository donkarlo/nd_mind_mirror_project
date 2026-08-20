from pathlib import Path


ROOT = Path("src/nd_mind_mirror")


def test_visual_quote_serializes_as_backslash_quote() -> None:
    visual = (ROOT / "ui/editor/latex/latex_visual_editor.py").read_text(encoding="utf-8")
    assert "'\"': r'\\\"'" in visual


def test_visual_roundtrip_formats_canonical_source_automatically() -> None:
    latex = (ROOT / "ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    assert "formatted_source = self._formatter.format(source)" in latex
    assert "cursor.insertText(formatted_source)" in latex


def test_preview_highlight_prefers_selection_or_current_word_and_disambiguates_duplicates() -> None:
    latex = (ROOT / "ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    main = (ROOT / "ui/window/main/main_window.py").read_text(encoding="utf-8")
    qml = (ROOT / "ui/preview/pdf/selectable_pdf_view.qml").read_text(encoding="utf-8")
    assert "active_preview_highlight_text" in latex
    assert "if cursor.hasSelection()" in latex
    assert "offset - 2" in latex and "offset + 2" in latex
    assert "editor.active_preview_highlight_text()" in main
    assert 'candidate.pageSearchResultsColor = "transparent"' in qml
    assert "chooseNearestHighlightResult" in qml
    assert "pdfView.searchModel.currentResult = best" in qml


def test_navigator_delete_key_deletes_selected_path() -> None:
    navigator = (ROOT / "ui/panel/file_system/file_system_panel.py").read_text(encoding="utf-8")
    assert "Qt.Key.Key_Delete" in navigator
    assert "self._delete_path(target)" in navigator


def test_source_and_visual_expose_direct_edit_in_ipad_for_existing_graphics() -> None:
    source = (ROOT / "ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    visual = (ROOT / "ui/editor/latex/latex_visual_editor.py").read_text(encoding="utf-8")
    assert '"Edit image in iPad…"' in source
    assert '"Edit image in iPad…"' in visual
    assert 'operation="update"' in source


def test_terminal_app_has_runtime_brain_mirror_taskbar_icon() -> None:
    app = (ROOT / "app/mind_mirror_application.py").read_text(encoding="utf-8")
    icon = (ROOT / "ui/icon/mind_mirror_icon.py").read_text(encoding="utf-8")
    assert "build_mind_mirror_icon" in app
    assert "application.setWindowIcon(icon)" in app
    assert "window.setWindowIcon(icon)" in app
    # Desktop-file installation is intentionally kept out of the Ubuntu 20.04
    # startup path; the packaged icon is still applied directly to Qt windows.
    assert "ensure_linux_desktop_integration" not in app
    assert "nd-mind-mirror.desktop" not in icon  # filename is composed from the desktop id
    assert "QPainterPath" not in icon
    assert "resources" in icon and "mind_mirror.png" in icon
    assert 'data_home / "applications"' in icon
