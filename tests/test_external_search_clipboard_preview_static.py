from pathlib import Path


def test_search_refreshes_for_external_workspace_changes_on_open():
    source = Path(
        "src/nd_mind_mirror/ui/search/window/search_window.py"
    ).read_text(encoding="utf-8")
    show_block = source.split("def show_and_focus", 1)[1].split("def apply_settings", 1)[0]
    assert "self.rebuild_index()" in show_block


def test_navigator_has_one_shot_clipboard_image_save_and_collision_names():
    panel = Path(
        "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py"
    ).read_text(encoding="utf-8")
    saver = Path(
        "src/nd_mind_mirror/core/clipboard/image/clipboard_image_saver.py"
    ).read_text(encoding="utf-8")
    assert 'base_name="img"' in panel
    assert 'extension=".jpg"' in panel
    assert "_last_saved_clipboard_generation" in panel
    assert 'f"{base_name}_{counter}{suffix}"' in saver


def test_pdf_preview_has_explicit_non_fading_scrollbars_for_overflow():
    qml = Path(
        "src/nd_mind_mirror/ui/preview/pdf/selectable_pdf_view.qml"
    ).read_text(encoding="utf-8")
    assert "id: explicitHorizontalBar" in qml
    assert "id: explicitVerticalBar" in qml
    assert "visible: root.explicitHorizontalOverflow" in qml
    assert "visible: root.explicitVerticalOverflow" in qml
    assert "policy: ScrollBar.AlwaysOn" in qml
