from pathlib import Path
import importlib.util
import random


def _project_file(relative: str) -> Path:
    test_path = Path(__file__).resolve()
    root = test_path.parent.parent
    return root / relative


def test_public_text_editor_uses_native_rich_qtextedit_layout() -> None:
    wrapper = _project_file(
        "src/nd_mind_mirror/ui/editor/base/text_editor.py"
    ).read_text(encoding="utf-8")
    rich_core = _project_file(
        "src/nd_mind_mirror/ui/editor/base/text_editor_rich_core.py"
    ).read_text(encoding="utf-8")

    assert "class TextEditor(RichTextEditor):" in wrapper
    assert "SourcePlainTextDocumentLayout" not in wrapper
    assert "setDocumentLayout" not in wrapper
    assert "def set_large_document_mode" in wrapper
    assert "class TextEditor(QTextEdit):" in rich_core
    assert "block_format.setLayoutDirection(direction)" in rich_core


def test_large_source_uses_rich_window_and_incremental_buffer() -> None:
    wrapper = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    ).read_text(encoding="utf-8")
    incremental_core = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor_incremental_core.py"
    ).read_text(encoding="utf-8")

    assert "IncrementalLargeLatexEditor" in wrapper
    assert "QTextEdit.setPlainText" in wrapper
    assert "editor_source_virtualization_threshold_chars" in wrapper
    assert "_DEFAULT_SOURCE_WINDOW_CHARS = 40_000" in wrapper

    assert "contentsChange.connect(" in incremental_core
    assert "self._synchronize_visible_change" in incremental_core
    assert "self._source_buffer.apply_edit(" in incremental_core
    assert "textChanged.connect(self._synchronize_visible_window)" not in incremental_core


def test_windowed_visual_commit_replaces_canonical_source_not_qtextdocument() -> None:
    wrapper = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    ).read_text(encoding="utf-8")

    method = wrapper.split("def _apply_visual_source", 1)[1].split(
        "def _synchronize_visible_change", 1
    )[0]
    assert "self._source_buffer.replace_source(canonical_source)" in method
    assert "self._load_visible_window(canonical_modified=True)" in method
    assert "QTextCursor(self.document())" not in method
    assert "cursor.select(QTextCursor.SelectionType.Document)" not in method


def test_incremental_buffer_matches_reference_string() -> None:
    path = _project_file(
        "src/nd_mind_mirror/core/document/latex/large/latex_source_buffer.py"
    )
    spec = importlib.util.spec_from_file_location("latex_source_buffer_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    random_generator = random.Random(7)
    reference = "\n".join(
        f"line {index} " + ("x" * random_generator.randint(0, 60))
        for index in range(900)
    )
    buffer = module.LatexSourceBuffer(120_000, 40_000)
    buffer.set_source(reference)

    for _ in range(300):
        position = random_generator.randint(0, len(reference))
        removed = random_generator.randint(
            0,
            min(5, len(reference) - position),
        )
        inserted = "".join(
            random_generator.choice("abc\n")
            for _ in range(random_generator.randint(0, 4))
        )
        buffer.apply_edit(position, removed, inserted)
        reference = (
            reference[:position]
            + inserted
            + reference[position + removed:]
        )
        assert buffer.source == reference
