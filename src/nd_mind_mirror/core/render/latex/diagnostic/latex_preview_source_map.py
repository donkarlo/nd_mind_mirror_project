from pathlib import Path
import re

from nd_mind_mirror.core.render.latex.diagnostic.latex_preview_source_location import (
    LatexPreviewSourceLocation,
)


class LatexPreviewSourceMap:
    """Map generated ``preview.tex`` lines back to canonical source files."""

    _BEGIN_PATTERN = re.compile(
        r"^\s*%\s*----\s+nd_mind_mirror\s+(?:input|include)\s+begin:\s*"
        r"(?P<path>.+?);.*----\s*$"
    )
    _END_PATTERN = re.compile(
        r"^\s*%\s*----\s+nd_mind_mirror\s+(?:input|include)\s+end:\s*"
        r"(?P<path>.+?)\s+----\s*$"
    )
    _DOCUMENT_BEGIN_PATTERN = re.compile(r"\\begin\s*\{document\}")
    _HEADING_PREFIX_PATTERN = re.compile(
        r"^\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?"
    )

    def __init__(
        self,
        prepared_source: str,
        master_path: str | Path,
        master_source: str,
    ) -> None:
        self._prepared_source = str(prepared_source)
        self._lines = self._prepared_source.splitlines()
        self._master_path = Path(master_path).expanduser().resolve(strict=False)
        self._source_by_path: dict[Path, str] = {
            self._master_path: str(master_source),
        }
        self._contexts = self._build_contexts()
        self._master_line_offset = self._find_master_line_offset(master_source)

    @property
    def prepared_source(self) -> str:
        return self._prepared_source

    def location_for_preview_line(self, preview_line: int) -> LatexPreviewSourceLocation:
        line_number = max(1, min(int(preview_line), max(len(self._lines), 1)))
        context = self._deepest_context(line_number)
        source_path = context[2] if context is not None else self._master_path
        source = self._source_for(source_path)
        preview_text = self._lines[line_number - 1] if self._lines else ""

        fallback = self._fallback_source_line(line_number, context, source)
        matched = self._match_source_line(source, preview_text, fallback)
        source_line = matched if matched is not None else fallback
        return LatexPreviewSourceLocation(
            source_path=source_path,
            line=source_line,
            column=1,
            preview_line=line_number,
        )

    def _build_contexts(self) -> list[tuple[int, int, Path, int]]:
        contexts: list[tuple[int, int, Path, int]] = []
        stack: list[tuple[int, Path, int]] = []
        for index, line in enumerate(self._lines, start=1):
            begin = self._BEGIN_PATTERN.match(line)
            if begin is not None:
                path = Path(begin.group("path")).expanduser().resolve(strict=False)
                stack.append((index, path, len(stack) + 1))
                self._source_for(path)
                continue

            end = self._END_PATTERN.match(line)
            if end is None or not stack:
                continue
            ending_path = Path(end.group("path")).expanduser().resolve(strict=False)
            for stack_index in range(len(stack) - 1, -1, -1):
                start, path, depth = stack[stack_index]
                if path != ending_path:
                    continue
                del stack[stack_index:]
                contexts.append((start, index, path, depth))
                break
        return contexts

    def _deepest_context(self, preview_line: int) -> tuple[int, int, Path, int] | None:
        candidates = [
            item
            for item in self._contexts
            if item[0] < preview_line < item[1]
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[3])

    def _fallback_source_line(
        self,
        preview_line: int,
        context: tuple[int, int, Path, int] | None,
        source: str,
    ) -> int:
        if context is None:
            return max(preview_line - self._master_line_offset, 1)

        start, _end, path, _depth = context
        effective = self._effective_lines_between(start + 1, preview_line, path)
        return self._body_start_line(source) + max(effective - 1, 0)

    def _effective_lines_between(self, first: int, last: int, path: Path) -> int:
        count = 0
        line_number = first
        candidates = sorted(
            (
                item
                for item in self._contexts
                if item[2] != path and item[0] >= first and item[1] <= last
            ),
            key=lambda item: (item[0], -item[1]),
        )
        nested = []
        for item in candidates:
            if any(
                parent[0] < item[0] and item[1] < parent[1]
                for parent in candidates
            ):
                continue
            nested.append(item)
        nested_index = 0
        while line_number <= last:
            if nested_index < len(nested) and nested[nested_index][0] == line_number:
                count += 1
                line_number = nested[nested_index][1] + 1
                nested_index += 1
                continue
            count += 1
            line_number += 1
        return max(count, 1)

    def _find_master_line_offset(self, master_source: str) -> int:
        source_lines = master_source.splitlines()
        for source_index, source_line in enumerate(source_lines, start=1):
            normalized = self._normalize_line(source_line)
            if not normalized or normalized.startswith("\\input{") or normalized.startswith("\\include{"):
                continue
            matches = [
                preview_index
                for preview_index, preview_line in enumerate(self._lines, start=1)
                if self._normalize_line(preview_line) == normalized
            ]
            if matches:
                return matches[0] - source_index
        return 0

    def _match_source_line(
        self,
        source: str,
        preview_text: str,
        fallback: int,
    ) -> int | None:
        target = self._normalize_line(preview_text)
        if not target or target.startswith("% ---- nd_mind_mirror"):
            return None
        candidates = [
            index
            for index, line in enumerate(source.splitlines(), start=1)
            if self._normalize_line(line) == target
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda value: abs(value - fallback))

    def _source_for(self, path: Path) -> str:
        cached = self._source_by_path.get(path)
        if cached is not None:
            return cached
        for encoding in ("utf-8", "latin-1"):
            try:
                value = path.read_text(encoding=encoding)
                self._source_by_path[path] = value
                return value
            except UnicodeDecodeError:
                continue
            except OSError:
                break
        self._source_by_path[path] = ""
        return ""

    def _body_start_line(self, source: str) -> int:
        match = self._DOCUMENT_BEGIN_PATTERN.search(source)
        if match is None:
            return 1
        return source.count("\n", 0, match.end()) + 1

    def _normalize_line(self, line: str) -> str:
        value = line.strip()
        value = self._HEADING_PREFIX_PATTERN.sub("\\<heading>", value)
        return re.sub(r"\s+", " ", value)
