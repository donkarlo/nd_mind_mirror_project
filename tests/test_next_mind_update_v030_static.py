from pathlib import Path


ROOT = Path("src/nd_mind_mirror")


def test_visual_underscore_and_quote_are_escaped_only_in_latex_source() -> None:
    visual = (ROOT / "ui/editor/latex/latex_visual_editor.py").read_text(encoding="utf-8")
    assert '"_": r"\\_"' in visual
    assert "'\"': r'\\\"'" in visual
    assert 'r"\\_": "_"' in visual


def test_all_source_editors_share_explicit_ide_line_shortcuts_and_undo_redo() -> None:
    base = (ROOT / "ui/editor/base/text_editor.py").read_text(encoding="utf-8")
    latex = (ROOT / "ui/editor/latex/latex_editor.py").read_text(encoding="utf-8")
    visual = (ROOT / "ui/editor/latex/latex_visual_editor.py").read_text(encoding="utf-8")
    assert "def _handle_common_editor_shortcut" in base
    assert "self._copy_current_line()" in base
    assert "self._cut_current_line()" in base
    assert "self._duplicate_current_line()" in base
    assert "self.undo()" in base and "self.redo()" in base
    assert "if self._handle_common_editor_shortcut(event):" in latex
    assert "self.undo()" in visual and "self.redo()" in visual


def test_navigator_context_menu_can_copy_absolute_path_and_name() -> None:
    navigator = (ROOT / "ui/panel/file_system/file_system_panel.py").read_text(encoding="utf-8")
    assert '"Copy Absolute Path"' in navigator
    assert '"Copy File Name"' in navigator
    assert "str(path.expanduser().resolve())" in navigator
    assert "self._clipboard.setText(path.name)" in navigator


def test_taskbar_uses_direct_brain_mirror_icon_instead_of_generic_gear() -> None:
    icon = (ROOT / "ui/icon/mind_mirror_icon.py").read_text(encoding="utf-8")
    assert 'f"Icon={icon_value}"' in icon
    assert '"StartupNotify=true"' in icon
    assert '"StartupWMClass=nd_mind_mirror_project"' in icon
    assert "installed_icon" in icon


def test_ipad_websocket_uses_network_framework_to_avoid_urlsession_ats_block() -> None:
    bridge = (ROOT / "graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClient.swift").read_text(encoding="utf-8")
    assert "import Network" in bridge
    assert "NWProtocolWebSocket.Options" in bridge
    assert "NWConnection(to: .url(url), using: parameters)" in bridge
    assert "URLSessionWebSocketTask" not in bridge
