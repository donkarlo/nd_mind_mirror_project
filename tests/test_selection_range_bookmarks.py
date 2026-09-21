from nd_mind_mirror.core.bookmark.range.range_bookmark_tracker import (
    RangeBookmarkTracker,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_selection_resolver import (
    RangeBookmarkSelectionResolver,
)
from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_editor_mixin import (
    SelectionRangeBookmarkEditorMixin,
)


class _Cursor:
    def __init__(self, start: int, end: int, text: str) -> None:
        self._start = int(start)
        self._end = int(end)
        self._text = str(text)

    def hasSelection(self) -> bool:
        return self._end > self._start

    def selectionStart(self) -> int:
        return self._start

    def selectionEnd(self) -> int:
        return self._end

    def selectedText(self) -> str:
        return self._text


class _Visual:
    def __init__(
        self,
        cursor: _Cursor,
        rough_anchor: tuple[int, int],
        rough_position: tuple[int, int],
        serialized: str,
    ) -> None:
        self._cursor = cursor
        self._rough_anchor = rough_anchor
        self._rough_position = rough_position
        self._serialized = serialized

    def textCursor(self):
        return self._cursor

    def source_selection_locations(self):
        return self._rough_anchor, self._rough_position

    def _selected_latex_source(self, _cursor) -> str:
        return self._serialized


class _Editor:
    def __init__(
        self,
        source: str,
        *,
        mode: str,
        cursor: _Cursor | None = None,
        visual: _Visual | None = None,
        window_start: int = 0,
    ) -> None:
        self._source = source
        self._edit_mode = mode
        self._cursor = cursor
        self._visual_editor = visual
        self.source_is_windowed = window_start > 0
        self.source_window_start = window_start

    def textCursor(self):
        return self._cursor

    def toPlainText(self) -> str:
        return self._source


class _FixedResolver:
    def __init__(self, value):
        self._value = value

    def resolve(self, _editor):
        return self._value


class _SelectionHarness(SelectionRangeBookmarkEditorMixin):
    pass


def test_source_selection_uses_exact_character_offsets():
    source = "alpha beta gamma"
    editor = _Editor(
        source,
        mode="source",
        cursor=_Cursor(6, 10, "beta"),
    )
    assert RangeBookmarkSelectionResolver().resolve(editor) == (6, 10)


def test_windowed_source_selection_adds_only_window_offset():
    source = "x" * 100 + "beta" + "y" * 20
    editor = _Editor(
        source,
        mode="source",
        cursor=_Cursor(3, 7, "beta"),
        window_start=97,
    )
    assert RangeBookmarkSelectionResolver().resolve(editor) == (100, 104)


def test_visual_short_selection_does_not_expand_to_rough_paragraph():
    source = "alpha beta gamma delta"
    cursor = _Cursor(6, 10, "beta")
    visual = _Visual(
        cursor,
        rough_anchor=(1, 1),
        rough_position=(1, len(source) + 1),
        serialized="beta",
    )
    editor = _Editor(source, mode="visual", visual=visual)

    assert RangeBookmarkSelectionResolver().resolve(editor) == (6, 10)


def test_visual_short_selection_without_exact_match_rejects_broad_fallback():
    source = "a" * 300
    cursor = _Cursor(1, 5, "beta")
    visual = _Visual(
        cursor,
        rough_anchor=(1, 1),
        rough_position=(1, 301),
        serialized="beta",
    )
    editor = _Editor(source, mode="visual", visual=visual)

    assert RangeBookmarkSelectionResolver().resolve(editor) is None


def test_visual_short_selection_without_exact_match_rejects_small_rough_fallback():
    source = "alpha gamma delta"
    cursor = _Cursor(1, 5, "beta")
    visual = _Visual(
        cursor,
        rough_anchor=(1, 1),
        rough_position=(1, len(source) + 1),
        serialized="beta",
    )
    editor = _Editor(source, mode="visual", visual=visual)

    assert RangeBookmarkSelectionResolver().resolve(editor) is None


def test_partial_overlap_is_not_treated_as_same_bookmark():
    harness = object.__new__(_SelectionHarness)
    harness._range_bookmark_tracker = RangeBookmarkTracker("abcdef")
    harness._range_bookmark_tracker.collection.add(0, 6, "abcdef")
    harness._range_bookmark_selection_resolver = _FixedResolver((2, 4))

    state = harness.range_bookmark_menu_context()

    assert state["action"] == "add"
    assert state["bookmark_id"] == ""


def test_no_selection_has_no_bookmark_action():
    harness = object.__new__(_SelectionHarness)
    harness._range_bookmark_tracker = RangeBookmarkTracker("abcdef")
    harness._range_bookmark_selection_resolver = _FixedResolver(None)

    assert harness.range_bookmark_menu_context()["action"] == "none"
