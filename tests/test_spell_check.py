"""Regression coverage for document-language spell checking."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QMenu

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.core.spell.spell_check_candidate_extractor import (
    SpellCheckCandidateExtractor,
)
from nd_mind_mirror.core.spell.spell_check_engine import SpellCheckEngine
from nd_mind_mirror.core.spell.spell_check_language_detector import (
    SpellCheckLanguageDetector,
)
from nd_mind_mirror.core.spell.spell_check_preference_store import (
    SpellCheckPreferenceStore,
)
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.decoration.editor_decoration_properties import (
    EditorDecorationProperties,
)
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.spell.spell_check_highlighter import (
    SpellCheckHighlighter,
)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])
def test_source_extractor_ignores_latex_only_regions() -> None:
    extractor = SpellCheckCandidateExtractor()
    source = (
        "\\documentclass{articlle}\n"
        "\\usepackage{grapihcx}\n"
        "\\section{Developmnt}\n"
        "This is a recieve test and eine Entwiklung.\n"
        "% commmentt\n"
        "Math $fomrula$ and \\label{wrnoglabel}\n"
    )
    words = [word for _start, _end, word in extractor.source_candidates(source)]
    assert "Developmnt" in words
    assert "recieve" in words
    assert "Entwiklung" in words
    assert "articlle" not in words
    assert "grapihcx" not in words
    assert "commmentt" not in words
    assert "fomrula" not in words
    assert "wrnoglabel" not in words


def test_engine_uses_only_selected_language(tmp_path: Path) -> None:
    engine = SpellCheckEngine(tmp_path / "dictionary")
    assert engine.is_correct("development", "en")
    assert engine.is_correct("Entwicklung", "de")
    assert not engine.is_correct("phonem", "en")
    assert "phoneme" in engine.suggestions("phonem", "en", limit=5)
    assert engine.is_correct("Phonem", "de")
def test_persian_dictionary_is_loaded_only_when_selected(tmp_path: Path) -> None:
    engine = SpellCheckEngine(tmp_path / "dictionary")
    engine.is_correct("development", "en")
    assert "fa" not in engine._dictionaries
    engine.is_correct("سلام", "fa")
    assert "fa" in engine._dictionaries


def test_language_detector_selects_one_document_language(tmp_path: Path) -> None:
    engine = SpellCheckEngine(tmp_path / "dictionary")
    detector = SpellCheckLanguageDetector()
    english = "The motifs are discovered independently at each phoneme level".split()
    german = "Die Motive werden unabhängig auf jeder Ebene entdeckt".split()
    assert detector.detect(english, engine) == "en"
    assert detector.detect(german, engine) == "de"


def test_custom_dictionary_is_language_specific(tmp_path: Path) -> None:
    engine = SpellCheckEngine(tmp_path / "dictionary")
    word = "ndmindmirrorword"
    assert not engine.is_correct(word, "en")
    assert engine.add_to_dictionary("en", word)
    assert engine.is_correct(word, "en")
    assert not engine.is_correct(word, "de")
def test_preferences_are_per_file_and_store_language(tmp_path: Path) -> None:
    settings_path = tmp_path / "session.ini"
    store = SpellCheckPreferenceStore(settings_path)
    first = tmp_path / "one.tex"
    second = tmp_path / "two.tex"
    assert store.is_enabled(first)
    assert store.language(first) == "auto"
    store.set_enabled(first, False)
    store.set_language(first, "de")
    assert not store.is_enabled(first)
    assert store.language(first) == "de"
    assert store.is_enabled(second)
    assert store.language(second) == "auto"


def test_english_document_offers_phoneme_for_phonem(tmp_path: Path) -> None:
    app = _application()
    settings = YamlSettings()
    editor = LatexEditor([], tmp_path / "english.tex", settings)
    editor.set_content(
        "Return the motifs discovered independently at each phonem level. "
        "The method compares every motif with a reference pattern."
    )
    controller = editor._spell_check_controller
    controller.set_enabled(True)
    assert controller.effective_language == "en"

    menu = QMenu()
    position = editor.toPlainText().index("phonem") + 2
    actions = controller.append_context_actions(
        menu,
        editor,
        position,
        source_mode=True,
    )
    labels = [action.text() for action, _callback in actions]
    assert "phoneme" in labels
    controller.set_enabled(False)
    editor.deleteLater()
    app.processEvents()
def test_source_suggestion_action_replaces_misspelling(tmp_path: Path) -> None:
    app = _application()
    editor = LatexEditor([], tmp_path / "source.tex", YamlSettings())
    editor.set_content("guided leanring")
    controller = editor._spell_check_controller
    controller.set_language_mode("en")
    menu = QMenu()
    position = editor.toPlainText().index("leanring") + 2
    actions = controller.append_context_actions(
        menu, editor, position, source_mode=True
    )
    learning = next(action for action, _callback in actions if action.text() == "learning")
    learning.trigger()
    assert editor.toPlainText() == "guided learning"
    editor.deleteLater()
    app.processEvents()


def test_visual_suggestion_action_replaces_misspelling(tmp_path: Path) -> None:
    app = _application()
    editor = LatexEditor([], tmp_path / "visual.tex", YamlSettings())
    editor.set_content("guided leanring")
    editor.set_edit_mode("visual")
    visual = editor._visual_editor
    controller = editor._spell_check_controller
    controller.set_language_mode("en")
    position = visual.toPlainText().index("leanring") + 2
    menu = QMenu()
    actions = controller.append_context_actions(
        menu, visual, position, source_mode=False
    )
    learning = next(action for action, _callback in actions if action.text() == "learning")
    learning.trigger()
    assert "learning" in visual.toPlainText()
    assert "leanring" not in visual.toPlainText()
    editor.deleteLater()
    app.processEvents()


def test_spell_decoration_survives_current_line_refresh() -> None:
    app = _application()
    editor = TextEditor()
    editor.setPlainText("A misspeled word")
    highlighter = SpellCheckHighlighter()
    highlighter.apply(editor, [(2, 11)])

    cursor = QTextCursor(editor.document())
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    editor._highlight_current_line()

    spell = [
        selection
        for selection in editor.extraSelections()
        if bool(
            selection.format.property(EditorDecorationProperties.SPELL_CHECK)
        )
    ]
    assert len(spell) == 1
    assert spell[0].cursor.selectedText() == "misspeled"
    editor.deleteLater()
    app.processEvents()
