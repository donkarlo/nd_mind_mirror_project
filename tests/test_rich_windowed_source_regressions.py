from pathlib import Path


def _project_file(relative: str) -> Path:
    return Path(__file__).resolve().parent.parent / relative


def test_persian_source_direction_uses_native_qtextedit_block_format() -> None:
    rich_core = _project_file(
        "src/nd_mind_mirror/ui/editor/base/text_editor_rich_core.py"
    ).read_text(encoding="utf-8")
    public_editor = _project_file(
        "src/nd_mind_mirror/ui/editor/base/text_editor.py"
    ).read_text(encoding="utf-8")

    assert "class TextEditor(QTextEdit):" in rich_core
    assert "block_format.setLayoutDirection(direction)" in rich_core
    assert "Qt.AlignmentFlag.AlignRight" in rich_core
    assert "SourcePlainTextDocumentLayout" not in public_editor


def test_source_graphic_space_uses_native_block_top_margin() -> None:
    controller = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller_core.py"
    ).read_text(encoding="utf-8")
    large_wrapper = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    ).read_text(encoding="utf-8")

    assert "block_format.setTopMargin" in controller
    assert "QTextEdit.setPlainText" in large_wrapper
    assert "LatexSourceBuffer" in large_wrapper


def test_python_qplaintext_document_layout_override_is_not_wired() -> None:
    public_editor = _project_file(
        "src/nd_mind_mirror/ui/editor/base/text_editor.py"
    ).read_text(encoding="utf-8")
    assert "QPlainTextDocumentLayout" not in public_editor
    assert "setDocumentLayout" not in public_editor
