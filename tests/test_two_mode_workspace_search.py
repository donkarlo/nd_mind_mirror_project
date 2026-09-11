"""Regression checks for the two-tab workspace search feature."""

from pathlib import Path
import ast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_WINDOW = PROJECT_ROOT / "src/nd_mind_mirror/ui/search/window/search_window.py"
SCOPE_PICKER = PROJECT_ROOT / "src/nd_mind_mirror/ui/search/window/search_scope_picker.py"
TEXT_TAB = PROJECT_ROOT / "src/nd_mind_mirror/ui/search/window/text_search_tab.py"
TEXT_WORKER = PROJECT_ROOT / "src/nd_mind_mirror/ui/search/thread/text_file_search_thread.py"
NAVIGATOR = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/window/main/search_aware_navigator_multi_path_context_controller.py"
)
WINDOW = PROJECT_ROOT / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"{name} not found in {path}")


def test_search_window_has_file_and_text_tabs() -> None:
    source = SEARCH_WINDOW.read_text(encoding="utf-8")
    assert '"Files & Folders"' in source
    assert '"Text in Files"' in source
    assert "TextSearchTab(" in source
    assert "SearchScopePicker(" in source


def test_folder_scope_is_read_only_and_uses_native_folder_chooser() -> None:
    source = SCOPE_PICKER.read_text(encoding="utf-8")
    assert "setReadOnly(True)" in source
    assert "QFileDialog.getExistingDirectory" in source


def test_each_search_mode_persists_its_own_query_and_root() -> None:
    file_source = SEARCH_WINDOW.read_text(encoding="utf-8")
    text_source = TEXT_TAB.read_text(encoding="utf-8")
    assert '"search/files/query"' in file_source
    assert '"search/files/root_path"' in file_source
    assert '"search/text/query"' in text_source
    assert '"search/text/root_path"' in text_source


def test_text_worker_collects_multiple_occurrences_and_latex_hierarchy() -> None:
    source = TEXT_WORKER.read_text(encoding="utf-8")
    assert "while len(occurrences) < remaining:" in source
    for heading in (
        "part", "chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph"
    ):
        assert heading in source
    assert '"structure": tuple(latex_structure)' in source


def test_text_result_activation_emits_exact_file_line_and_column() -> None:
    activate = _function_source(TEXT_TAB, "_activate_item")
    assert "location_selected.emit" in activate
    assert "path_text" in activate and "line" in activate and "column" in activate
    opener = _function_source(WINDOW, "_open_search_text_location")
    assert "self._open_path" in opener
    assert "go_to_location" in opener


def test_navigator_folder_context_menu_exposes_both_search_modes() -> None:
    show_menu = _function_source(NAVIGATOR, "show_menu")
    assert "if path.is_dir():" in show_menu
    assert '"Search Files / Folders Here"' in show_menu
    assert '"Search Text in Files Here"' in show_menu
