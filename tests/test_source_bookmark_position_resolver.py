"""Regression tests for windowed bookmark position safety."""

from nd_mind_mirror.ui.editor.bookmark.source_bookmark_position_resolver import (
    SourceBookmarkPositionResolver,
)


class _Document:
    def __init__(self, character_count: int) -> None:
        self._character_count = int(character_count)

    def characterCount(self) -> int:
        return self._character_count


class _NormalEditor:
    source_is_windowed = False

    def __init__(self) -> None:
        self._document = _Document(101)

    def document(self):
        return self._document

    def _source_position_for_location(self, location):
        return int(location[0])


class _WindowedEditor:
    source_is_windowed = True

    def __init__(self, mapping) -> None:
        self._mapping = dict(mapping)
        self._document = _Document(81)

    def document(self):
        return self._document

    def _source_position_for_location(self, location):
        raise AssertionError("full canonical position must not be used")

    def _local_position_for_location(self, location):
        return self._mapping.get(tuple(location))


def test_normal_editor_uses_document_position() -> None:
    resolver = SourceBookmarkPositionResolver()
    editor = _NormalEditor()

    assert resolver.resolve(editor, (42, 1)) == 42


def test_windowed_editor_uses_local_position() -> None:
    resolver = SourceBookmarkPositionResolver()
    editor = _WindowedEditor({(5000, 1): 37})

    assert resolver.resolve(editor, (5000, 1)) == 37


def test_off_window_bookmark_is_not_materialized() -> None:
    resolver = SourceBookmarkPositionResolver()
    editor = _WindowedEditor({})

    assert resolver.resolve(editor, (5000, 1)) is None


def test_out_of_range_position_is_rejected_before_qtextcursor() -> None:
    resolver = SourceBookmarkPositionResolver()
    editor = _WindowedEditor({(5000, 1): 153436})

    assert resolver.resolve(editor, (5000, 1)) is None
