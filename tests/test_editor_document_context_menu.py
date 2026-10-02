from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/nd_mind_mirror"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_real_source_and_visual_context_controllers_append_document_actions() -> None:
    source = _read(
        "ui/editor/bookmark/range/range_bookmark_source_context_controller.py"
    )
    visual = _read(
        "ui/editor/bookmark/range/range_bookmark_visual_context_controller.py"
    )
    assert 'getattr(editor.window(), "decorate_editor_menu", None)' in source
    assert "decorate_menu(menu, editor._source_path)" in source
    assert 'getattr(watched.window(), "decorate_editor_menu", None)' in visual
    assert "decorate_menu(menu, self._editor.source_path)" in visual


def test_document_file_menu_keeps_native_text_clipboard_actions_separate() -> None:
    navigator = _read(
        "ui/window/main/navigator_multi_path_context_controller.py"
    )
    method = navigator.split("def append_document_menu", 1)[1].split(
        "def _decorate_menu", 1
    )[0]
    for label in (
        'addMenu("Open")',
        'addMenu("Copy / Share")',
        'addMenu("Create")',
        'addMenu("Manage")',
        'addAction("Copy Absolute Path")',
        'addAction("Copy from Default Path")',
        'addAction("Copy File Name")',
        'addAction("Copy GitHub URL")',
        'addAction("Open GitHub URL")',
        'addAction("New LaTeX File…")',
        'addAction("New File…")',
        'addAction("New Folder…")',
        'addAction("Rename…")',
        'addAction("Delete…")',
    ):
        assert label in method
    assert 'addAction("Copy")' not in method
    assert 'addAction("Cut")' not in method
    assert 'addAction("Paste")' not in method
