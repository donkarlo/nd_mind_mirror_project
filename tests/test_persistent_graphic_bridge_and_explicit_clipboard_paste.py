"""Regressions for persistent iPad transport and explicit clipboard-image paste."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGURED = (
    ROOT
    / "src/nd_mind_mirror/graphic/bridge/configured_unified_server.py"
).read_text(encoding="utf-8")
FILE_SYSTEM_PANEL = (
    ROOT
    / "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py"
).read_text(encoding="utf-8")


def test_reverse_connector_recovers_without_pending_open_request() -> None:
    connector = CONFIGURED.split(
        "    async def _reverse_connector_loop", 1
    )[1].split(
        "    async def _watch_workspace", 1
    )[0]

    assert "if self.tcp_clients:" in connector
    assert "found = await self._discover_ipad_listener()" in connector
    assert "not self._has_pending_editor_request()" not in connector
    assert "_has_pending_editor_request" not in CONFIGURED


def test_navigator_left_click_never_pastes_clipboard_image() -> None:
    clicked = FILE_SYSTEM_PANEL.split(
        "    def _on_clicked", 1
    )[1].split(
        "    def _on_clipboard_changed", 1
    )[0]

    assert "_save_current_clipboard_image" not in clicked
    assert "self.state_changed.emit()" in clicked


def test_explicit_clipboard_image_paste_paths_remain_available() -> None:
    assert "Key.Key_V" in FILE_SYSTEM_PANEL
    assert "Paste Clipboard Image Here" in FILE_SYSTEM_PANEL
    assert "_save_current_clipboard_image(directory, one_shot=False)" in FILE_SYSTEM_PANEL
