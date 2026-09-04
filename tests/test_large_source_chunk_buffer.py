from nd_mind_mirror.core.document.latex.large.latex_source_buffer import (
    LatexSourceBuffer,
)


def _large_source(lines: int = 5000) -> str:
    return "".join(
        f"line {index:05d} — متن آزمایشی برای سند بزرگ\n"
        for index in range(lines)
    )


def test_window_edit_preserves_complete_canonical_source_without_eager_join():
    source = _large_source()
    buffer = LatexSourceBuffer(threshold_chars=1000, window_chars=12000)
    buffer.set_source(source, focus_position=len(source) // 2)

    start = buffer.window_start
    end = buffer.window_end
    visible = buffer.window_text
    marker = "INSERTED-WITHOUT-FULL-SOURCE-SPLICE"
    edited = visible[:100] + marker + visible[100:]
    expected = source[:start] + edited + source[end:]

    buffer.replace_window(edited)

    assert buffer._materialized_source is None
    assert marker in buffer.window_text
    assert "".join(buffer.snapshot_pieces()) == expected
    assert buffer._materialized_source is None
    assert buffer.source == expected


def test_line_position_mapping_survives_chunked_window_edits():
    source = _large_source(3000)
    buffer = LatexSourceBuffer(threshold_chars=1000, window_chars=10000)
    buffer.set_source(source, focus_position=len(source) // 3)

    edited = buffer.window_text.replace("line", "row", 3)
    buffer.replace_window(edited)
    full = buffer.source

    sample_lines = (1, 2, 100, 500, 1500, 2999)
    split = full.splitlines(keepends=True)
    for line_number in sample_lines:
        if line_number > len(split):
            continue
        position = sum(len(item) for item in split[: line_number - 1])
        mapped_line, mapped_column = buffer.location_for_full_position(position)
        assert mapped_line == line_number
        assert mapped_column == 1
        assert buffer.full_position_for_location(line_number, 1) == position


def test_source_window_can_shift_without_materializing_complete_source():
    source = _large_source(4000)
    buffer = LatexSourceBuffer(threshold_chars=1000, window_chars=9000)
    buffer.set_source(source, focus_position=0)

    assert buffer.has_content_after_window
    buffer._materialized_source = None
    old_start = buffer.window_start

    assert buffer.shift_window(1)
    assert buffer.window_start > old_start
    assert buffer._materialized_source is None

    assert buffer.shift_window(-1)
    assert buffer._materialized_source is None
