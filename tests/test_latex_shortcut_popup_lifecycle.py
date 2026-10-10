"""Regression checks for stray top-level LaTeX shortcut chooser windows."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget

from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import LatexShortcut
from nd_mind_mirror.ui.editor.latex.latex_shortcut_popup import LatexShortcutPopup


APP = QApplication.instance() or QApplication([])


def _new_popup():
    editor = QTextEdit()
    editor.setPlainText("item")
    editor.show()
    popup = LatexShortcutPopup(editor)
    popup.set_matches([
        LatexShortcut("item", "\\item ", "item of a list"),
        LatexShortcut("itemize", "\\begin{itemize}", "list"),
    ])
    popup.show_under_cursor()
    APP.processEvents()
    assert popup.isVisible()
    return editor, popup


def test_esc_sent_to_other_widget_closes_popup():
    editor, popup = _new_popup()
    other = QWidget()
    try:
        QTest.keyClick(other, Qt.Key.Key_Escape)
        assert not popup.isVisible()
    finally:
        popup.close()
        editor.close()


def test_click_outside_closes_popup_without_swallowing_click():
    editor, popup = _new_popup()
    other = QWidget()
    other.resize(300, 100)
    try:
        other.show()
        APP.processEvents()
        popup.show_under_cursor()
        assert popup.isVisible()
        QTest.mouseClick(other, Qt.MouseButton.LeftButton)
        assert not popup.isVisible()
    finally:
        other.close()
        popup.close()
        editor.close()


def test_wheel_outside_closes_popup():
    editor, popup = _new_popup()
    try:
        wheel = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate, False,
        )
        APP.sendEvent(editor.viewport(), wheel)
        assert not popup.isVisible()
    finally:
        popup.close()
        editor.close()


def test_editor_focus_loss_closes_popup():
    editor, popup = _new_popup()
    try:
        APP.sendEvent(editor, QFocusEvent(QEvent.Type.FocusOut))
        assert not popup.isVisible()
    finally:
        popup.close()
        editor.close()


def test_editor_hide_closes_popup():
    editor, popup = _new_popup()
    try:
        editor.hide()
        assert not popup.isVisible()
    finally:
        popup.close()
        editor.close()


def test_clicking_popup_item_emits_shortcut_and_closes():
    editor, popup = _new_popup()
    selected = []
    popup.shortcut_selected.connect(selected.append)
    try:
        target = popup._list.item(1)
        rect = popup._list.visualItemRect(target)
        QTest.mouseClick(popup._list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        assert selected and selected[0].trigger == "itemize"
        assert not popup.isVisible()
    finally:
        popup.close()
        editor.close()


def test_real_latex_editor_cursor_navigation_dismisses_popup(tmp_path):
    from PySide6.QtGui import QTextCursor
    from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
    from nd_mind_mirror.ui.editor.latex.core.latex_editor_core import LatexEditor

    editor = LatexEditor([], tmp_path / "test.tex", YamlSettings())
    try:
        editor.show()
        editor.set_content("\\begin{itemize}\n\\item item\n\\end{itemize}")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        editor._shortcut_popup.set_matches([
            LatexShortcut("item", "\\item ", "item of a list")
        ])
        editor._shortcut_popup.show_under_cursor()
        assert editor._shortcut_popup.isVisible()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        assert not editor._shortcut_popup.isVisible()
    finally:
        editor.close()


def test_real_latex_editor_mode_switch_dismisses_popup(tmp_path):
    from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
    from nd_mind_mirror.ui.editor.latex.core.latex_editor_core import LatexEditor

    editor = LatexEditor([], tmp_path / "test.tex", YamlSettings())
    try:
        editor.show()
        editor.set_content("\\item item")
        editor._shortcut_popup.set_matches([
            LatexShortcut("item", "\\item ", "item of a list")
        ])
        editor._shortcut_popup.show_under_cursor()
        assert editor._shortcut_popup.isVisible()
        editor.set_edit_mode("visual")
        assert not editor._shortcut_popup.isVisible()
    finally:
        editor.close()


def test_real_latex_editor_keeps_shortcut_typing_available(tmp_path):
    from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
    from nd_mind_mirror.ui.editor.latex.core.latex_editor_core import LatexEditor

    editor = LatexEditor([], tmp_path / "test.tex", YamlSettings())
    try:
        editor.show()
        editor.set_content("ite")
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        editor._shortcuts = [LatexShortcut("item", "\\item ", "item of a list")]
        editor._shortcut_popup.set_matches(editor._shortcuts)
        editor._update_shortcut_popup()
        assert editor._shortcut_popup.isVisible()
        QTest.keyClick(editor, Qt.Key.Key_M)
        assert editor.toPlainText() == "item"
        assert editor._shortcut_popup.isVisible()
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        assert not editor._shortcut_popup.isVisible()
        assert editor.toPlainText() == "item"
    finally:
        editor.close()
