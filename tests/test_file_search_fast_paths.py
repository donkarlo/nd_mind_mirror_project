"""Live file-search regression tests for direct paths, fuzzy fallback, and index reuse."""

import os
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.search.thread.cooperative_file_search_thread import (
    CooperativeFileSearchThread,
)
from nd_mind_mirror.ui.search.window.search_window import SearchWindow

APP = QApplication.instance() or QApplication([])


def _entry(path: Path, root: Path, directory: bool = False) -> tuple:
    name = path.name
    return (
        str(path), name, path.stem, name.casefold(),
        path.stem.casefold(), directory, path.relative_to(root).as_posix().casefold(),
    )


def _results(root: Path, entries: list[tuple], query: str) -> list:
    observed = []
    worker = CooperativeFileSearchThread(
        generation=3,
        entries=entries,
        query=query,
        max_results=50,
        fuzzy_threshold=0.86,
        root_path=root,
    )
    worker.results_ready.connect(
        lambda _generation, results, _truncated: observed.extend(results)
    )
    worker.run()
    return observed


def test_absolute_and_workspace_relative_paths_open_directly(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "chapter" / "one.tex"
    source.parent.mkdir(parents=True)
    source.write_text("Content", encoding="utf-8")

    for query in (str(source), "/chapter/one.tex", "chapter/one.tex"):
        assert _results(root, [], query) == [
            {"path": str(source), "is_directory": False}
        ]


def test_explicit_folder_path_retains_directory_type(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    directory = root / "chapter"
    directory.mkdir(parents=True)
    assert _results(root, [], str(directory)) == [
        {"path": str(directory), "is_directory": True}
    ]


def test_workspace_absolute_path_ignores_narrow_search_scope(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    selected_scope = root / "other"
    selected_scope.mkdir(parents=True)
    requested = root / "chapters" / "one.tex"
    requested.parent.mkdir()
    requested.write_text("", encoding="utf-8")
    observed = []
    worker = CooperativeFileSearchThread(
        generation=1, entries=[], query="/chapters/one.tex",
        max_results=20, fuzzy_threshold=0.86,
        root_path=selected_scope, workspace_root_path=root,
    )
    worker.results_ready.connect(lambda _gen, results, _limit: observed.extend(results))
    worker.run()
    assert observed == [{"path": str(requested), "is_directory": False}]


def test_exact_hierarchical_and_fuzzy_fallback(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    path = root / "signal_processing" / "autocorrelation.tex"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    entries = [_entry(path.parent, root, True), _entry(path, root)]

    for query in ("autocorrelation", "autocorrelatoin", "signal_processing > auto"):
        assert str(path) in _results(root, entries, query)
    assert _results(root, entries, "signal_processing/autocorrelation.tex") == [
        {"path": str(path), "is_directory": False}
    ]


def test_reopening_files_tab_preserves_a_ready_index(tmp_path: Path) -> None:
    app = APP
    window = SearchWindow(
        root_path=tmp_path,
        max_results=30,
        debounce_ms=280,
        ignore_file_path=tmp_path / "ignore.yaml",
        fuzzy_threshold=0.86,
        window_width=650,
        window_height=500,
        tree_indent_width=10,
    )
    try:
        deadline = time.monotonic() + 4
        while not window._index_ready and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert window._index_ready
        generation = window._index_generation
        window.show_and_focus()
        app.processEvents()
        window.close()
        app.processEvents()
        window.show_and_focus()
        app.processEvents()
        assert window._index_generation == generation
    finally:
        window.shutdown()
        window.close()


def test_external_absolute_file_can_be_opened_from_result_tree(tmp_path: Path) -> None:
    app = APP
    root = tmp_path / "repo"
    external = tmp_path / "outside" / "source.tex"
    root.mkdir()
    external.parent.mkdir()
    external.write_text("", encoding="utf-8")
    window = SearchWindow(
        root_path=root,
        max_results=30,
        debounce_ms=280,
        ignore_file_path=tmp_path / "ignore.yaml",
        fuzzy_threshold=0.86,
        window_width=650,
        window_height=500,
        tree_indent_width=10,
    )
    try:
        opened = []
        window.latex_file_selected.connect(opened.append)
        window._search_edit.setText(str(external))
        deadline = time.monotonic() + 3
        while window._displayed_query != str(external) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert window._displayed_query == str(external)
        parent_item = window._tree.topLevelItem(0)
        item = parent_item.child(0)
        assert item.text(0) == external.name
        assert item.toolTip(0) == str(external)
        window._activate_item(item)
        assert opened == [str(external)]
    finally:
        window.shutdown()
        window.close()
        app.processEvents()
