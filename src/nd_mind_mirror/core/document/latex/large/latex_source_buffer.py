from __future__ import annotations

from bisect import bisect_right


class LatexSourceBuffer:
    """Store canonical LaTeX source as chunks and apply edits incrementally.

    Normal typing replaces only the chunk or small group of chunks touched by
    the edit.  The complete source is joined lazily only when a consumer such
    as Preview, Structure, or explicit save actually requests it.
    """

    def __init__(self, threshold_chars: int, window_chars: int) -> None:
        self._threshold_chars = max(int(threshold_chars), 1)
        self._window_chars = max(int(window_chars), 8_000)
        self._chunk_chars = max(8_000, min(self._window_chars // 2, 24_000))
        self._chunks: list[str] = [""]
        self._newline_counts: list[int] = [0]
        self._char_offsets: list[int] = [0, 0]
        self._line_offsets: list[int] = [0, 0]
        self._window_first_chunk = 0
        self._window_last_chunk = 1
        self._materialized_source: str | None = ""
        self._revision = 0

    @property
    def source(self) -> str:
        if self._materialized_source is None:
            self._materialized_source = "".join(self._chunks)
        return self._materialized_source

    @property
    def revision(self) -> int:
        return int(self._revision)

    @property
    def total_length(self) -> int:
        return int(self._char_offsets[-1])

    @property
    def line_count(self) -> int:
        return int(self._line_offsets[-1]) + 1

    @property
    def is_windowed(self) -> bool:
        return self.total_length >= self._threshold_chars

    @property
    def window_start(self) -> int:
        return int(self._char_offsets[self._window_first_chunk])

    @property
    def window_end(self) -> int:
        return int(self._char_offsets[self._window_last_chunk])

    @property
    def window_text(self) -> str:
        return "".join(
            self._chunks[self._window_first_chunk:self._window_last_chunk]
        )

    @property
    def has_content_before_window(self) -> bool:
        return self._window_first_chunk > 0

    @property
    def has_content_after_window(self) -> bool:
        return self._window_last_chunk < len(self._chunks)

    def snapshot_pieces(self) -> tuple[str, ...]:
        return tuple(self._chunks)

    def set_source(self, source: str, focus_position: int = 0) -> None:
        value = str(source)
        self._chunks = self._split_text(value)
        self._newline_counts = [chunk.count("\n") for chunk in self._chunks]
        self._rebuild_offsets()
        self._materialized_source = value
        self._revision += 1
        self.select_around_position(focus_position)

    def apply_edit(
        self,
        local_position: int,
        chars_removed: int,
        inserted_text: str,
    ) -> None:
        """Apply an edit whose position is relative to the visible Source window."""
        old_window_start = self.window_start
        old_window_end = self.window_end
        local_limit = max(old_window_end - old_window_start, 0)
        local_start = max(0, min(int(local_position), local_limit))
        full_start = old_window_start + local_start
        self.apply_full_edit(full_start, chars_removed, inserted_text)

    def apply_full_edit(
        self,
        full_position: int,
        chars_removed: int,
        inserted_text: str,
    ) -> None:
        """Apply one canonical edit without rebuilding untouched chunks."""
        old_total = self.total_length
        old_first = self._window_first_chunk
        old_last = self._window_last_chunk
        old_window_end = self.window_end

        full_start = max(0, min(int(full_position), old_total))
        removed = max(int(chars_removed), 0)
        full_end = max(full_start, min(full_start + removed, old_total))

        if (
            self.is_windowed
            and full_start == old_window_end
            and old_last > old_first
        ):
            start_chunk = old_last - 1
        else:
            start_chunk = self._chunk_index_for_position(full_start)

        if full_end > full_start:
            end_chunk = self._chunk_index_for_position(full_end - 1)
        else:
            end_chunk = start_chunk

        segment_start = self._char_offsets[start_chunk]
        segment = "".join(self._chunks[start_chunk:end_chunk + 1])
        relative_start = max(0, min(full_start - segment_start, len(segment)))
        relative_end = max(
            relative_start,
            min(full_end - segment_start, len(segment)),
        )
        replacement = (
            segment[:relative_start]
            + str(inserted_text)
            + segment[relative_end:]
        )

        new_chunks = self._split_text(replacement)
        new_counts = [chunk.count("\n") for chunk in new_chunks]
        replaced_count = end_chunk - start_chunk + 1
        self._chunks[start_chunk:end_chunk + 1] = new_chunks
        self._newline_counts[start_chunk:end_chunk + 1] = new_counts

        if not self._chunks:
            self._chunks = [""]
            self._newline_counts = [0]

        chunk_delta = len(new_chunks) - replaced_count
        self._rebuild_offsets()

        if not self.is_windowed:
            self._window_first_chunk = 0
            self._window_last_chunk = len(self._chunks)
        else:
            first = max(0, min(old_first, len(self._chunks) - 1))
            last = old_last
            if start_chunk < old_last:
                last += chunk_delta
            self._window_first_chunk = first
            self._window_last_chunk = max(
                first + 1,
                min(last, len(self._chunks)),
            )

        self._materialized_source = None
        self._revision += 1

    def replace_window(self, window_text: str) -> None:
        self.apply_edit(
            0,
            max(self.window_end - self.window_start, 0),
            str(window_text),
        )

    def replace_source(self, source: str, focus_position: int = 0) -> None:
        self.set_source(source, focus_position=focus_position)

    def replace_source_incrementally(self, source: str) -> bool:
        """Apply the changed middle of a complete replacement source.

        Visual mode still emits one complete canonical string.  Comparing it
        with the current canonical source is cheap, while rebuilding every
        chunk on each Visual keystroke is not.  Keep the common prefix/suffix
        chunks and replace only the changed middle.
        """
        value = str(source)
        current = self.source
        if value == current:
            return False

        prefix = self._common_prefix_length(current, value)
        suffix = self._common_suffix_length(current, value, prefix)
        current_end = len(current) - suffix
        value_end = len(value) - suffix
        self.apply_full_edit(
            prefix,
            current_end - prefix,
            value[prefix:value_end],
        )
        return True

    def select_around_line(self, line_number: int) -> None:
        self.select_around_position(
            self.full_position_for_location(line_number, 1)
        )

    def select_around_position(self, position: int) -> None:
        if not self.is_windowed:
            self._window_first_chunk = 0
            self._window_last_chunk = len(self._chunks)
            return

        total = self.total_length
        focus = max(0, min(int(position), total))
        half = self._window_chars // 2
        target_start = max(focus - half, 0)
        target_end = min(focus + half, total)

        first = self._chunk_index_for_position(target_start)
        last_index = self._chunk_index_for_position(target_end)
        last = min(last_index + 1, len(self._chunks))

        while (
            first > 0
            and self._char_offsets[last] - self._char_offsets[first]
            < self._window_chars
        ):
            first -= 1
        while (
            last < len(self._chunks)
            and self._char_offsets[last] - self._char_offsets[first]
            < self._window_chars
        ):
            last += 1

        self._window_first_chunk = max(
            0,
            min(first, len(self._chunks) - 1),
        )
        self._window_last_chunk = max(
            self._window_first_chunk + 1,
            min(last, len(self._chunks)),
        )

    def shift_window(self, direction: int) -> bool:
        if not self.is_windowed:
            return False

        old = (self._window_first_chunk, self._window_last_chunk)
        if direction > 0:
            if not self.has_content_after_window:
                return False
            focus = min(
                self.window_end + self._window_chars // 3,
                self.total_length,
            )
        else:
            if not self.has_content_before_window:
                return False
            focus = max(
                self.window_start - self._window_chars // 3,
                0,
            )
        self.select_around_position(focus)
        return old != (self._window_first_chunk, self._window_last_chunk)

    def full_position_for_local_position(self, local_position: int) -> int:
        local = max(
            0,
            min(int(local_position), self.window_end - self.window_start),
        )
        return self.window_start + local

    def local_position_for_full_position(self, full_position: int) -> int | None:
        position = max(0, min(int(full_position), self.total_length))
        if not self.window_start <= position <= self.window_end:
            return None
        return position - self.window_start

    def location_for_full_position(self, position: int) -> tuple[int, int]:
        full = max(0, min(int(position), self.total_length))
        chunk_index = self._chunk_index_for_position(full)
        chunk_start = self._char_offsets[chunk_index]
        local = full - chunk_start
        chunk = self._chunks[chunk_index]

        line = (
            self._line_offsets[chunk_index]
            + chunk.count("\n", 0, local)
            + 1
        )
        column = self._column_at_chunk_offset(chunk_index, local)
        return int(line), int(column)

    def full_position_for_location(
        self,
        line_number: int,
        column: int = 1,
    ) -> int:
        line = max(1, min(int(line_number), self.line_count))
        column_value = max(int(column), 1)
        newlines_before_line = line - 1

        chunk_index = max(
            bisect_right(self._line_offsets, newlines_before_line) - 1,
            0,
        )
        chunk_index = min(chunk_index, len(self._chunks) - 1)

        while (
            chunk_index + 1 < len(self._chunks)
            and self._line_offsets[chunk_index + 1] <= newlines_before_line
        ):
            chunk_index += 1

        local_line_number = (
            newlines_before_line - self._line_offsets[chunk_index]
        )
        chunk = self._chunks[chunk_index]
        line_start = 0
        for _ in range(local_line_number):
            newline = chunk.find("\n", line_start)
            if newline < 0:
                break
            line_start = newline + 1

        newline = chunk.find("\n", line_start)
        line_end = len(chunk) if newline < 0 else newline
        local = min(line_start + column_value - 1, line_end)
        return self._char_offsets[chunk_index] + local

    def window_start_location(self) -> tuple[int, int]:
        return self.location_for_full_position(self.window_start)

    @staticmethod
    def _common_prefix_length(left: str, right: str) -> int:
        limit = min(len(left), len(right))
        index = 0
        block = 8_192
        while (
            index + block <= limit
            and left[index:index + block] == right[index:index + block]
        ):
            index += block
        while index < limit and left[index] == right[index]:
            index += 1
        return index

    @staticmethod
    def _common_suffix_length(left: str, right: str, prefix: int) -> int:
        limit = min(len(left), len(right)) - max(int(prefix), 0)
        suffix = 0
        block = 8_192
        while suffix + block <= limit:
            left_start = len(left) - suffix - block
            right_start = len(right) - suffix - block
            if (
                left[left_start:left_start + block]
                != right[right_start:right_start + block]
            ):
                break
            suffix += block
        while (
            suffix < limit
            and left[len(left) - suffix - 1] == right[len(right) - suffix - 1]
        ):
            suffix += 1
        return suffix

    def _chunk_index_for_position(self, position: int) -> int:
        if len(self._chunks) == 1:
            return 0
        full = max(0, min(int(position), self.total_length))
        if full >= self.total_length:
            return len(self._chunks) - 1
        index = bisect_right(self._char_offsets, full) - 1
        return max(0, min(index, len(self._chunks) - 1))

    def _column_at_chunk_offset(self, chunk_index: int, local: int) -> int:
        chunk = self._chunks[chunk_index]
        last_newline = chunk.rfind("\n", 0, local)
        if last_newline >= 0:
            return local - last_newline

        column = local + 1
        previous = chunk_index - 1
        while previous >= 0:
            text = self._chunks[previous]
            last_newline = text.rfind("\n")
            if last_newline >= 0:
                column += len(text) - last_newline - 1
                break
            column += len(text)
            previous -= 1
        return column

    def _split_text(self, text: str) -> list[str]:
        if not text:
            return [""]

        chunks: list[str] = []
        start = 0
        length = len(text)
        while start < length:
            target = min(start + self._chunk_chars, length)
            if target >= length:
                end = length
            else:
                newline = text.find("\n", target)
                end = length if newline < 0 else newline + 1
            chunks.append(text[start:end])
            start = end
        return chunks or [""]

    def _rebuild_offsets(self) -> None:
        char_offsets = [0]
        line_offsets = [0]
        char_total = 0
        line_total = 0
        for chunk, newline_count in zip(
            self._chunks,
            self._newline_counts,
        ):
            char_total += len(chunk)
            line_total += int(newline_count)
            char_offsets.append(char_total)
            line_offsets.append(line_total)
        self._char_offsets = char_offsets
        self._line_offsets = line_offsets
