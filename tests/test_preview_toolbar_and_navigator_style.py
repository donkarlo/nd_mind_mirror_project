"""Regression tests for Preview toolbar order and Navigator appearance settings."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_preview_toolbar_runtime_insertion_order() -> None:
    detach_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/preview_detach_controller.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/late_runtime_fixes.py"
    ).read_text(encoding="utf-8")

    assert "controls.insertWidget(2, self._detach_button)" in detach_source
    assert "_controls_layout.insertWidget(3, lock_button)" in runtime_source
    assert "_controls_layout.insertWidget(4, extend_button)" in runtime_source


def test_navigator_uses_independent_child_indent_setting() -> None:
    main_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/main_window.py"
    ).read_text(encoding="utf-8")
    settings_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/core/settings/yaml/yaml_settings_base.py"
    ).read_text(encoding="utf-8")

    assert "navigator_child_indent_width" in settings_source
    assert (
        "indent_width=self._app_settings.navigator_child_indent_width"
        in main_source
    )


def test_navigator_uses_modern_folder_icon_provider() -> None:
    panel_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py"
    ).read_text(encoding="utf-8")
    provider_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/icon/file_system/modern_folder_icon_provider.py"
    ).read_text(encoding="utf-8")

    assert "ModernFolderIconProvider()" in panel_source
    assert "folder_color=self._app_settings.navigator_folder_color" in (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/main_window.py"
    ).read_text(encoding="utf-8")
    assert '_DEFAULT_FOLDER_COLOR = "#69B7F4"' in provider_source
