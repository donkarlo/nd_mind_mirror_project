"""Regression tests for semantic editor Undo/Redo."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.window.main.undo_redo_controller import UndoRedoController


def _application() -> QApplication:
    """Return one Qt application for headless editor tests."""
    return QApplication.instance() or QApplication([])


def _add_invisible_block_format_step(editor: TextEditor) -> None:
    """Add a formatting-only undo entry like Mind Mirror's layout updater."""
    cursor = QTextCursor(editor.document().firstBlock())
    block_format = cursor.blockFormat()
    block_format.setTopMargin(block_format.topMargin() + 1.0)
    cursor.setBlockFormat(block_format)


def test_semantic_undo_skips_invisible_formatting_step() -> None:
    """Undo must remove typed text instead of only reverting block formatting."""
    _application()
    editor = TextEditor()
    editor.insertPlainText("x")
    _add_invisible_block_format_step(editor)

    UndoRedoController._run_command(editor, "undo")

    assert editor.toPlainText() == ""


def test_semantic_redo_restores_text_after_semantic_undo() -> None:
    """Redo must restore the visible edit after semantic Undo."""
    _application()
    editor = TextEditor()
    editor.insertPlainText("x")
    _add_invisible_block_format_step(editor)

    UndoRedoController._run_command(editor, "undo")
    UndoRedoController._run_command(editor, "redo")

    assert editor.toPlainText() == "x"


def test_context_menu_undo_uses_semantic_history() -> None:
    """Qt's right-click Undo action must use the same semantic controller."""
    _application()
    editor = TextEditor()
    controller = UndoRedoController()
    editor.insertPlainText("x")
    _add_invisible_block_format_step(editor)

    menu = editor.createStandardContextMenu()
    controller._patch_context_menu(menu)
    undo_action = next(
        action
        for action in menu.actions()
        if controller._context_action_command(action.text()) == "undo"
    )
    undo_action.trigger()

    assert editor.toPlainText() == ""
