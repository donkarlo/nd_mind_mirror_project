"""Resolve and maintain local LaTeX file references across the workspace."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


class ReferenceOccurrence:
    """One supported LaTeX command that points to a local file."""

    __slots__ = (
        "command", "raw_target", "target_path", "target_start", "target_end",
        "command_start", "command_end", "click_start", "click_end", "line",
        "column", "referring_file",
    )

    def __init__(
        self,
        command: str,
        raw_target: str,
        target_path: Path | None,
        target_start: int,
        target_end: int,
        command_start: int,
        command_end: int,
        click_start: int,
        click_end: int,
        line: int,
        column: int,
        referring_file: Path,
    ) -> None:
        self.command = command
        self.raw_target = raw_target
        self.target_path = target_path
        self.target_start = target_start
        self.target_end = target_end
        self.command_start = command_start
        self.command_end = command_end
        self.click_start = click_start
        self.click_end = click_end
        self.line = line
        self.column = column
        self.referring_file = referring_file


class WorkspaceReferenceResolver:
    """Use absolute, current-file-relative, then default-path-relative lookup."""

    _TEXT_SUFFIXES = {
        ".tex", ".tikz", ".bib", ".yaml", ".yml", ".md", ".txt", ".py",
        ".sh", ".json", ".toml", ".ini", ".cfg",
    }
    _SKIP_DIRECTORIES = {".git", ".idea", "__pycache__", ".pytest_cache"}
    _REMOTE_PREFIXES = ("http://", "https://", "mailto:", "data:", "ftp://", "#")
    _MAX_FILE_SIZE = 8 * 1024 * 1024
    _HREF = re.compile(
        r"\\(?P<command>href)\*?(?:\s*\[[^\]\n]*\])?\s*"
        r"\{(?P<target>[^{}\n]+)\}\s*\{(?P<label>[^{}\n]*)\}"
    )
    _ONE = re.compile(
        r"\\(?P<command>input|include|subfile|includegraphics|includepdf|"
        r"addbibresource|lstinputlisting|verbatiminput|VerbatimInput|url)"
        r"\*?(?:\s*\[[^\]\n]*\])?\s*\{(?P<target>[^{}\n]+)\}"
    )
    _MINTED = re.compile(
        r"\\(?P<command>inputminted)(?:\s*\[[^\]\n]*\])?\s*"
        r"\{[^{}\n]+\}\s*\{(?P<target>[^{}\n]+)\}"
    )
    _MARKERS = (
        "\\href", "\\url", "\\input", "\\include", "\\subfile",
        "\\includegraphics", "\\includepdf", "\\addbibresource",
        "\\lstinputlisting", "\\verbatiminput", "\\VerbatimInput",
        "\\inputminted",
    )
    _SUFFIXES = {
        "input": (".tex",), "include": (".tex",), "subfile": (".tex",),
        "addbibresource": (".bib",),
        "includegraphics": (".pdf", ".png", ".jpg", ".jpeg", ".svg", ".webp"),
    }

    def __init__(self, default_path: str | Path | None = None) -> None:
        self.set_default_path(default_path)

    @property
    def default_path(self) -> Path | None:
        return self._default_path

    def set_default_path(self, default_path: str | Path | None) -> None:
        self._default_path = (
            self._safe(Path(default_path).expanduser())
            if default_path not in (None, "")
            else None
        )

    @staticmethod
    def _safe(path: Path) -> Path:
        try:
            return path.resolve(strict=False)
        except OSError:
            return Path(os.path.abspath(os.fspath(path)))

    @classmethod
    def _local(cls, token: str) -> bool:
        value = token.strip()
        return bool(value) and not value.casefold().startswith(cls._REMOTE_PREFIXES)

    @staticmethod
    def _path_token(token: str) -> Path:
        value = token.strip().replace(r"\_", "_")
        if value.casefold().startswith("file:"):
            parsed = urlparse(value)
            value = unquote(parsed.path or "")
        return Path(value).expanduser()

    def candidate_paths(
        self, token: str, referring_file: str | Path
    ) -> list[tuple[str, Path]]:
        raw = self._path_token(token)
        referring = self._safe(Path(referring_file).expanduser())
        if raw.is_absolute():
            return [("absolute", self._safe(raw))]
        candidates = [("file_relative", self._safe(referring.parent / raw))]
        if self._default_path is not None:
            candidates.append(("default_relative", self._safe(self._default_path / raw)))
        seen: set[Path] = set()
        return [
            (kind, path)
            for kind, path in candidates
            if not (path in seen or seen.add(path))
        ]

    def resolve(
        self,
        token: str,
        referring_file: str | Path,
        command: str = "",
        require_exists: bool = True,
    ) -> Path | None:
        if not self._local(token):
            return None
        suffixes = self._SUFFIXES.get(command, ())
        for _kind, candidate in self.candidate_paths(token, referring_file):
            variants = [candidate]
            if not candidate.suffix:
                variants.extend(candidate.with_suffix(suffix) for suffix in suffixes)
            for variant in variants:
                if not require_exists or variant.exists():
                    return variant
        return None

    def match_candidate(
        self,
        token: str,
        referring_file: str | Path,
        target_root: str | Path,
        suffix_hint: str = "",
    ) -> tuple[str, Path, bool] | None:
        if not self._local(token):
            return None
        target = self._safe(Path(target_root).expanduser())
        omitted = bool(suffix_hint and not self._path_token(token).suffix)
        for kind, candidate in self.candidate_paths(token, referring_file):
            variants = [(candidate, False)]
            if omitted:
                variants.append((candidate.with_suffix(suffix_hint), True))
            for variant, used_suffix in variants:
                if self._same_or_child(self._safe(variant), target):
                    return kind, self._safe(variant), used_suffix
        return None

    @staticmethod
    def _same_or_child(candidate: Path, root: Path) -> bool:
        if candidate == root:
            return True
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    def occurrences(
        self,
        source: str,
        referring_file: str | Path,
        require_exists: bool = True,
    ) -> list[ReferenceOccurrence]:
        if not source or not any(marker in source for marker in self._MARKERS):
            return []
        referring = self._safe(Path(referring_file).expanduser())
        output: list[ReferenceOccurrence] = []
        used: list[tuple[int, int]] = []
        for pattern in (self._HREF, self._MINTED, self._ONE):
            for match in pattern.finditer(source):
                if any(match.start() < end and match.end() > start for start, end in used):
                    continue
                command = match.group("command")
                raw_target = match.group("target")
                target = self.resolve(
                    raw_target, referring, command=command, require_exists=require_exists
                )
                if target is None and require_exists:
                    continue
                target_start, target_end = match.span("target")
                line = source.count("\n", 0, match.start()) + 1
                previous = source.rfind("\n", 0, match.start())
                column = match.start() + 1 if previous < 0 else match.start() - previous
                output.append(
                    ReferenceOccurrence(
                        command, raw_target, target, target_start, target_end,
                        match.start(), match.end(), match.start(), match.end(),
                        line, column, referring,
                    )
                )
                used.append((match.start(), match.end()))
        return output

    @staticmethod
    def source_offset(source: str, line: int, column: int) -> int:
        line = max(int(line), 1)
        column = max(int(column), 1)
        lines = source.splitlines(keepends=True)
        if not lines:
            return 0
        index = min(line - 1, len(lines) - 1)
        base = sum(len(value) for value in lines[:index])
        return min(base + column - 1, base + len(lines[index].rstrip("\r\n")))

    def occurrence_at(
        self, source: str, referring_file: str | Path, offset: int
    ) -> ReferenceOccurrence | None:
        cursor = max(0, min(int(offset), len(source)))
        for occurrence in self.occurrences(source, referring_file, require_exists=True):
            if occurrence.click_start <= cursor <= occurrence.click_end:
                return occurrence
        return None

    def rewrite_preview_links(
        self, source: str, referring_file: str | Path | None
    ) -> str:
        if referring_file is None or not source:
            return source
        output = source
        occurrences = self.occurrences(source, referring_file, require_exists=True)
        for occurrence in reversed(occurrences):
            if occurrence.command not in {"href", "url"} or occurrence.target_path is None:
                continue
            output = (
                output[:occurrence.target_start]
                + occurrence.target_path.as_uri()
                + output[occurrence.target_end:]
            )
        return output

    def find_usages(
        self,
        workspace_root: str | Path,
        target_path: str | Path,
        ignore_file_path: str | Path | None = None,
    ) -> list[ReferenceOccurrence]:
        from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher

        root = self._safe(Path(workspace_root).expanduser())
        target = self._safe(Path(target_path).expanduser())
        matcher = SearchIgnoreMatcher.from_file(ignore_file_path)
        output: list[ReferenceOccurrence] = []
        if not root.is_dir():
            return output
        for directory, dirnames, filenames in os.walk(root):
            directory_path = Path(directory)
            dirnames[:] = [
                name for name in dirnames
                if name not in self._SKIP_DIRECTORIES
                and not matcher.is_ignored(directory_path / name, root, is_directory=True)
            ]
            for name in filenames:
                candidate = directory_path / name
                if candidate.suffix.lower() not in self._TEXT_SUFFIXES:
                    continue
                if matcher.is_ignored(candidate, root, is_directory=False):
                    continue
                try:
                    if candidate.stat().st_size > self._MAX_FILE_SIZE:
                        continue
                    text = candidate.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue
                for occurrence in self.occurrences(text, candidate, require_exists=False):
                    match = self.match_candidate(
                        occurrence.raw_target,
                        candidate,
                        target,
                        suffix_hint=target.suffix if target.suffix else "",
                    )
                    if match is not None:
                        occurrence.target_path = match[1]
                        output.append(occurrence)
        return output

    def remove_references(
        self, source: str, referring_file: str | Path, target_path: str | Path
    ) -> str:
        target = self._safe(Path(target_path).expanduser())
        matches = [
            occurrence
            for occurrence in self.occurrences(source, referring_file, require_exists=False)
            if self.match_candidate(
                occurrence.raw_target,
                referring_file,
                target,
                suffix_hint=target.suffix if target.suffix else "",
            ) is not None
        ]
        spans: list[tuple[int, int]] = []
        for occurrence in matches:
            figure = self._figure_span(source, referring_file, target, occurrence)
            spans.append(figure or (occurrence.command_start, occurrence.command_end))
        output = source
        for start, end in reversed(self._merge(spans)):
            output = output[:start] + output[end:]
        output = re.sub(r"(?m)^[ \t]+$", "", output)
        return re.sub(r"\n{3,}", "\n\n", output)

    def _figure_span(
        self,
        source: str,
        referring_file: str | Path,
        target: Path,
        occurrence: ReferenceOccurrence,
    ) -> tuple[int, int] | None:
        if occurrence.command != "includegraphics":
            return None
        begin = source.rfind(r"\begin{figure", 0, occurrence.command_start)
        end_marker = r"\end{figure}"
        end = source.find(end_marker, occurrence.command_end)
        if begin < 0 or end < 0:
            return None
        block_end = end + len(end_marker)
        block = source[begin:block_end]
        graphics = [item for item in self.occurrences(block, referring_file, False) if item.command == "includegraphics"]
        if len(graphics) != 1:
            return None
        if self.match_candidate(
            graphics[0].raw_target, referring_file, target, target.suffix
        ) is None:
            return None
        start = source.rfind("\n", 0, begin) + 1
        line_end = source.find("\n", block_end)
        return start, (len(source) if line_end < 0 else line_end + 1)

    @staticmethod
    def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
        ordered = sorted({span for span in spans if span[1] > span[0]})
        merged: list[tuple[int, int]] = []
        for start, end in ordered:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged
