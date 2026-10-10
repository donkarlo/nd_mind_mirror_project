"""Visual Enter must survive a source reload without rewriting other lines."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor


APP = QApplication.instance() or QApplication([])


def test_visual_enter_preserves_linebreak_across_reload() -> None:
    source = (
        "\\documentclass{extarticle}\n\\begin{document}\n\n"
        "   \\section{عنوان}\n\n"
        "      یک متن فارسی نمونه که خط اول است.\n"
        "      خط دوم همان پاراگراف است.\n\n"
        "\\end{document}\n"
    )
    editor = LatexVisualEditor()
    try:
        editor.load_source(source)
        assert editor.serialized_source() == source
        block = editor.document().firstBlock()
        while block.isValid() and "یک متن" not in block.text():
            block = block.next()
        assert block.isValid()
        split_at = block.text().index("نمونه")
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + split_at)
        editor.setTextCursor(cursor)
        editor.keyPressEvent(QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "\n",
        ))
        updated = editor.serialized_source()
        assert "      یک متن فارسی \nنمونه که خط اول است." in updated
        assert "      خط دوم همان پاراگراف است." in updated
        editor.load_source(updated)
        assert editor.serialized_source() == updated
    finally:
        editor.close()


def test_visual_preserves_multiple_newlines_and_indentation() -> None:
    source = (
        "\\begin{document}\n\n"
        "      Text one\n"
        "\n\n"
        "  Text two\n\n"
        "\\end{document}"
    )
    editor = LatexVisualEditor()
    try:
        editor.load_source(source)
        assert editor.serialized_source() == source
    finally:
        editor.close()
