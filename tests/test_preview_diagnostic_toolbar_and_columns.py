"""Regression checks for diagnostics copy menu scope and column resizing."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ERROR_PANEL = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/preview/latex/error/latex_error_panel.py"
)
ERROR_TREE = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/preview/latex/error/latex_error_tree.py"
)
UNDO_CONTROLLER = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/window/main/undo_redo_controller.py"
)


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"{name} not found in {path}")


def test_copy_button_is_in_title_row_and_menu_contains_only_export_formats() -> None:
    source = ERROR_PANEL.read_text(encoding="utf-8")
    assert "title_row.addWidget(self._copy_button)" in source
    assert "layout.addWidget(self._hint)" in source
    assert "copy_menu.addAction(self._copy_text_action)" in source
    assert "copy_menu.addAction(self._copy_yaml_action)" in source
    assert "Undo" not in source
    assert "Redo" not in source


def test_trace_location_header_divider_is_interactive() -> None:
    source = ERROR_TREE.read_text(encoding="utf-8")
    assert "setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)" in source
    assert "setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)" in source
    assert "header.resizeSection(0, 420)" in source
    assert "border-right: 1px solid" in source


def test_undo_redo_context_patch_uses_menu_owner_not_focused_editor() -> None:
    patch_source = _function_source(UNDO_CONTROLLER, "_patch_context_menu")
    menu_resolver = _function_source(UNDO_CONTROLLER, "_supported_menu_view")
    assert "self._supported_menu_view(menu)" in patch_source
    assert "menu.parentWidget()" in menu_resolver
    assert "QApplication.focusWidget" not in menu_resolver
