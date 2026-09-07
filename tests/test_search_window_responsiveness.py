"""Regression checks for non-blocking Double-Shift search architecture."""

from pathlib import Path
import ast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_WINDOW = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "search"
    / "window"
    / "search_window.py"
)
PRESENTER = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "search"
    / "window"
    / "search_result_tree_presenter.py"
)
SEARCH_WORKER = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "search"
    / "thread"
    / "cooperative_file_search_thread.py"
)
INDEX_WORKER = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "search"
    / "thread"
    / "file_search_index_thread.py"
)


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return "\n".join(
                lines[node.lineno - 1:node.end_lineno]
            )

    raise AssertionError(
        f"Function {function_name} not found in {path}"
    )


def test_rebuild_and_close_do_not_wait_on_gui_thread() -> None:
    rebuild = _function_source(
        SEARCH_WINDOW,
        "rebuild_index",
    )
    close_event = _function_source(
        SEARCH_WINDOW,
        "closeEvent",
    )

    assert ".wait(" not in rebuild
    assert ".wait(" not in close_event


def test_repeated_double_shift_does_not_rebuild_or_select_query() -> None:
    show_and_focus = _function_source(
        SEARCH_WINDOW,
        "show_and_focus",
    )

    assert "if was_visible:" in show_and_focus
    assert "return" in show_and_focus
    assert show_and_focus.index("if was_visible:") < show_and_focus.index(
        "self._search_edit.selectAll()"
    )


def test_result_presentation_does_not_stat_dropbox_paths() -> None:
    populate = _function_source(
        PRESENTER,
        "populate",
    )

    assert ".is_dir(" not in populate
    assert ".exists(" not in populate
    assert ".resolve(" not in populate
    assert "setUpdatesEnabled(False)" in populate


def test_search_workers_yield_the_gil_during_large_jobs() -> None:
    search_source = SEARCH_WORKER.read_text(
        encoding="utf-8"
    )
    index_source = INDEX_WORKER.read_text(
        encoding="utf-8"
    )

    assert "QThread.msleep(1)" in search_source
    assert "QThread.msleep(1)" in index_source


def test_legacy_large_document_controller_index_name_is_supported() -> None:
    source = SEARCH_WINDOW.read_text(encoding="utf-8")

    assert "def _index_thread(self):" in source
    assert "@_index_thread.setter" in source
    assert "self._legacy_index_thread = None" in source
    assert "self._index_threads.append(thread)" in source


def test_typing_cancels_legacy_background_index_refresh() -> None:
    schedule = _function_source(
        SEARCH_WINDOW,
        "_schedule_search",
    )

    assert "legacy_index_thread" in schedule
    assert "requestInterruption()" in schedule
