"""Regression checks for Navigator ownership, pinned Ctrl+W, and fresh bridge startup."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (
    ROOT / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")
OWNER = (
    ROOT / "src/nd_mind_mirror/ui/window/main/navigator_multi_path_ownership_controller.py"
).read_text(encoding="utf-8")
CLOSE = (
    ROOT / "src/nd_mind_mirror/ui/window/main/current_editor_tab_close_controller.py"
).read_text(encoding="utf-8")
BRIDGE = (
    ROOT / "src/nd_mind_mirror/graphic/core/bridge_session_process_controller.py"
).read_text(encoding="utf-8")


def test_navigator_multi_path_controller_is_final_runtime_owner() -> None:
    assert "NavigatorMultiPathOwnershipController(" in MAIN
    assert "NavigatorClipboardShortcutController(" not in MAIN
    assert "QTimer.singleShot(0, self.activate)" in OWNER
    assert "SelectionMode.ExtendedSelection" in OWNER
    assert 'self._shortcut("Ctrl+C"' in OWNER
    assert 'self._shortcut("Ctrl+X"' in OWNER
    assert 'self._shortcut("Ctrl+V"' in OWNER
    assert "customContextMenuRequested.disconnect()" in OWNER
    assert "self._context_controller.show_menu" in OWNER


def test_ctrl_w_explicitly_closes_pinned_tabs_and_restores_pin_on_cancel() -> None:
    assert 'getattr(self._window, "_pinned_tab_controller", None)' in CLOSE
    assert "pinned_controller.unpin_path(path)" in CLOSE
    assert "self._editor_panel.request_close_current_tab()" in CLOSE
    assert "self._editor_panel._index_for_path(path) >= 0" in CLOSE
    assert "pinned_controller.pin_path(path)" in CLOSE


def test_application_session_starts_current_bridge_even_when_default_port_is_busy() -> None:
    assert "GraphicBridgeSessionProcessController(" in MAIN
    assert '"-m",' in BRIDGE
    assert '"nd_mind_mirror.graphic.bridge"' in BRIDGE
    assert '"--workspace"' in BRIDGE
    assert "_port_is_open" not in BRIDGE
