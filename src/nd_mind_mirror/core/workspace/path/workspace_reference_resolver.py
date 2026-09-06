"""Resolve and maintain local file references across the configured workspace."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


class ReferenceOccurrence:
    """One supported path-bearing command occurrence."""

    __slots__ = (
        "command",
        "raw_target",
        "target_path",
        "target_start",
        "target_end",
        "command_start",
        "command_end",
        "click_start",
        "click_end",
        "line",
        "column",
        "referring_file",
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
    """Resolve one path with file-relative, default-rooted, and system semantics."""

    _TEXT_SUFFIXES = {
        ".tex",
        ".ltx",
        ".sty",
        ".cls",
        ".tikz",
        ".bib",
        ".yaml",
        ".yml",
        ".md",
        ".markdown",
        ".html",
        ".htm",
        ".txt",
        ".py",
        ".sh",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
    }
    _SKIP_DIRECTORIES = {".git", ".idea", "__pycache__", ".pytest_cache"}
    _REMOTE_PREFIXES = ("http://", "https://", "mailto:", "data:", "ftp://", "#")
    _MAX_FILE_SIZE = 8 * 1024 * 1024
    _LIST_COMMANDS = {"bibliography", "includeonly"}

    _HREF = re.compile(
        r"\\(?P<command>href)\*?(?:\s*\[[^\]\n]*\])?\s*"
        r"\{(?P<target>[^{}\n]+)\}\s*\{(?P<label>[^{}\n]*)\}"
    )
    _ONE = re.compile(
        r"\\(?P<command>input|include|subfile|includegraphics|includepdf|"
        r"addbibresource|lstinputlisting|verbatiminput|VerbatimInput|url)"
        r"\*?(?:\s*\[[^\]\n]*\])?\s*\{(?P<target>[^{}\n]+)\}"
    )
    _LIST = re.compile(
        r"\\(?P<command>bibliography|includeonly)"
        r"\*?(?:\s*\[[^\]\n]*\])?\s*\{(?P<target>[^{}\n]+)\}"
    )
    _MINTED = re.compile(
        r"\\(?P<command>inputminted)(?:\s*\[[^\]\n]*\])?\s*"
        r"\{[^{}\n]+\}\s*\{(?P<target>[^{}\n]+)\}"
    )
    _MARKERS = (
        "\\href",
        "\\url",
        "\\input",
        "\\include",
        "\\subfile",
        "\\includegraphics",
        "\\includepdf",
        "\\addbibresource",
        "\\bibliography",
        "\\includeonly",
        "\\lstinputlisting",
        "\\verbatiminput",
        "\\VerbatimInput",
        "\\inputminted",
    )
    _SUFFIXES = {
        "input": (".tex",),
        "include": (".tex",),
        "subfile": (".tex",),
        "bibliography": (".bib",),
        "addbibresource": (".bib",),
        "includepdf": (".pdf",),
        "includegraphics": (
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".svg",
            ".webp",
            ".eps",
        ),
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

    def is_local_reference(self, token: str) -> bool:
        """Return whether a token names a local filesystem resource."""
        return self._local(token)

    @staticmethod
    def _path_token(token: str) -> Path:
        value = token.strip().replace(r"\_", "_")
        if value.casefold().startswith("file:"):
            parsed = urlparse(value)
            value = unquote(parsed.path or "")
        return Path(value).expanduser()

    def _repository_root(self) -> Path | None:
        """Return the nearest configured workspace ancestor named ``repo``."""
        if self._default_path is None:
            return None
        for candidate in (self._default_path, *self._default_path.parents):
            if candidate.name == "repo":
                return candidate
        return None

    def _repository_alias_candidate(self, raw: Path) -> Path | None:
        """Map ``/repo/...`` to the configured repository root."""
        raw_text = raw.as_posix()
        if raw_text != "/repo" and not raw_text.startswith("/repo/"):
            return None
        repository_root = self._repository_root()
        if repository_root is None:
            return None
        relative_text = raw_text[len("/repo") :].lstrip("/")
        return self._safe(repository_root / relative_text)

    def candidate_paths(
        self,
        token: str,
        referring_file: str | Path,
    ) -> list[tuple[str, Path]]:
        """Return candidates in the three configured path modes.

        Relative tokens are checked beside the referring file first. A leading
        slash is workspace-rooted against ``search.default_path`` before being
        interpreted as a real operating-system absolute path. ``/repo`` keeps
        its explicit repository alias semantics.
        """
        raw = self._path_token(token)
        referring = self._safe(Path(referring_file).expanduser())
        repository_alias = self._repository_alias_candidate(raw)
        if repository_alias is not None:
            return [("repository_alias", repository_alias)]

        candidates: list[tuple[str, Path]] = []
        if raw.is_absolute():
            if self._default_path is not None:
                rooted_relative = raw.as_posix().lstrip("/")
                candidates.append(
                    ("default_rooted", self._safe(self._default_path / rooted_relative))
                )
            candidates.append(("absolute", self._safe(raw)))
        else:
            candidates.append(("file_relative", self._safe(referring.parent / raw)))
            if self._default_path is not None:
                candidates.append(("default_relative", self._safe(self._default_path / raw)))

        seen: set[Path] = set()
        return [
            (kind, path)
            for kind, path in candidates
            if not (path in seen or seen.add(path))
        ]

    def _candidate_variants(self, candidate: Path, command: str) -> list[Path]:
        variants = [candidate]
        if candidate.suffix:
            return variants
        for suffix in self._SUFFIXES.get(command, ()):
            variants.append(candidate.with_suffix(suffix))
        if command in {"input", "include", "subfile"} and candidate.name:
            variants.append(candidate / f"{candidate.name}.tex")
        return variants

    def resolve(
        self,
        token: str,
        referring_file: str | Path,
        command: str = "",
        require_exists: bool = True,
    ) -> Path | None:
        if not self._local(token):
            return None

        all_variants: list[Path] = []
        for _kind, candidate in self.candidate_paths(token, referring_file):
            variants = self._candidate_variants(candidate, command)
            all_variants.extend(variants)
            for variant in variants:
                try:
                    if variant.exists():
                        return self._safe(variant)
                except OSError:
                    continue

        if require_exists or not all_variants:
            return None
        return self._safe(all_variants[0])

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
                resolved = self._safe(variant)
                if self._same_or_child(resolved, target):
                    return kind, resolved, used_suffix
        return None

    def format_path(
        self,
        path: str | Path,
        kind: str,
        referring_file: str | Path,
    ) -> str | None:
        """Render a moved target using the same path style as its reference."""
        resolved = self._safe(Path(path).expanduser())
        referring = self._safe(Path(referring_file).expanduser())

        if kind == "absolute":
            return resolved.as_posix()
        if kind == "file_relative":
            return os.path.relpath(resolved, referring.parent).replace(os.sep, "/")
        if kind == "repository_alias":
            repository_root = self._repository_root()
            if repository_root is None:
                return None
            try:
                relative = resolved.relative_to(repository_root).as_posix()
            except ValueError:
                return None
            return "/repo" if not relative else f"/repo/{relative}"
        if kind in {"default_rooted", "default_relative"}:
            if self._default_path is None:
                return None
            try:
                relative = resolved.relative_to(self._default_path).as_posix()
            except ValueError:
                return None
            if kind == "default_rooted":
                return "/" if not relative else f"/{relative}"
            return relative
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
                occurrence = self._single_occurrence(
                    source,
                    match,
                    referring,
                    require_exists,
                )
                if occurrence is not None:
                    output.append(occurrence)
                used.append((match.start(), match.end()))

        for match in self._LIST.finditer(source):
            if any(match.start() < end and match.end() > start for start, end in used):
                continue
            command = match.group("command")
            target_start, _target_end = match.span("target")
            for item, item_start, item_end in self._split_list_targets(
                match.group("target"),
                target_start,
            ):
                target = self.resolve(
                    item,
                    referring,
                    command=command,
                    require_exists=require_exists,
                )
                if target is None and require_exists:
                    continue
                line, column = self._line_column(source, match.start())
                output.append(
                    ReferenceOccurrence(
                        command,
                        item,
                        target,
                        item_start,
                        item_end,
                        match.start(),
                        match.end(),
                        item_start,
                        item_end,
                        line,
                        column,
                        referring,
                    )
                )
            used.append((match.start(), match.end()))

        return sorted(output, key=lambda item: (item.command_start, item.target_start))

    def _single_occurrence(
        self,
        source: str,
        match: re.Match[str],
        referring: Path,
        require_exists: bool,
    ) -> ReferenceOccurrence | None:
        command = match.group("command")
        raw_target = match.group("target")
        target = self.resolve(
            raw_target,
            referring,
            command=command,
            require_exists=require_exists,
        )
        if target is None and require_exists:
            return None
        target_start, target_end = match.span("target")
        line, column = self._line_column(source, match.start())
        return ReferenceOccurrence(
            command,
            raw_target,
            target,
            target_start,
            target_end,
            match.start(),
            match.end(),
            match.start(),
            match.end(),
            line,
            column,
            referring,
        )

    @staticmethod
    def _split_list_targets(value: str, absolute_start: int) -> list[tuple[str, int, int]]:
        result: list[tuple[str, int, int]] = []
        offset = 0
        for raw_item in value.split(","):
            leading = len(raw_item) - len(raw_item.lstrip())
            trailing = len(raw_item.rstrip())
            item = raw_item.strip()
            if item:
                start = absolute_start + offset + leading
                end = absolute_start + offset + trailing
                result.append((item, start, end))
            offset += len(raw_item) + 1
        return result

    @staticmethod
    def _line_column(source: str, offset: int) -> tuple[int, int]:
        line = source.count("\n", 0, offset) + 1
        previous = source.rfind("\n", 0, offset)
        column = offset + 1 if previous < 0 else offset - previous
        return line, column

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
        self,
        source: str,
        referring_file: str | Path,
        offset: int,
    ) -> ReferenceOccurrence | None:
        cursor = max(0, min(int(offset), len(source)))
        for occurrence in self.occurrences(source, referring_file, require_exists=True):
            if occurrence.click_start <= cursor <= occurrence.click_end:
                return occurrence
        return None

    def rewrite_preview_links(
        self,
        source: str,
        referring_file: str | Path | None,
    ) -> str:
        if referring_file is None or not source:
            return source
        output = source
        occurrences = self.occurrences(source, referring_file, require_exists=True)
        for occurrence in reversed(occurrences):
            if occurrence.command not in {"href", "url"} or occurrence.target_path is None:
                continue
            output = (
                output[: occurrence.target_start]
                + occurrence.target_path.as_uri()
                + output[occurrence.target_end :]
            )
        return output

    def rewrite_paths_for_preview(
        self,
        source: str,
        referring_file: str | Path,
    ) -> str:
        """Rewrite non-structural local references to concrete filesystem paths."""
        output = source
        structural_commands = {"input", "include", "subfile", "includeonly"}
        occurrences = self.occurrences(source, referring_file, require_exists=True)
        for occurrence in reversed(occurrences):
            if occurrence.command in structural_commands or occurrence.target_path is None:
                continue
            if occurrence.command in {"href", "url"}:
                replacement = occurrence.target_path.as_uri()
            else:
                replacement = occurrence.target_path.as_posix()
                if (
                    occurrence.command == "bibliography"
                    and not Path(occurrence.raw_target).suffix
                    and replacement.endswith(".bib")
                ):
                    replacement = replacement[:-4]
            output = (
                output[: occurrence.target_start]
                + replacement
                + output[occurrence.target_end :]
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
                name
                for name in dirnames
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
        self,
        source: str,
        referring_file: str | Path,
        target_path: str | Path,
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
            )
            is not None
        ]
        if not matches:
            return source

        edits: list[tuple[int, int, str]] = []
        list_groups: dict[tuple[int, int], list[ReferenceOccurrence]] = {}
        for occurrence in matches:
            if occurrence.command in self._LIST_COMMANDS:
                list_groups.setdefault(
                    (occurrence.command_start, occurrence.command_end), []
                ).append(occurrence)
                continue
            figure = self._figure_span(source, referring_file, target, occurrence)
            start, end = figure or (occurrence.command_start, occurrence.command_end)
            edits.append((start, end, ""))

        for command_span, command_matches in list_groups.items():
            replacement = self._remove_list_items(
                source,
                command_span,
                command_matches,
            )
            edits.append((command_span[0], command_span[1], replacement))

        output = source
        for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
            output = output[:start] + replacement + output[end:]
        output = re.sub(r"(?m)^[ \t]+$", "", output)
        return re.sub(r"\n{3,}", "\n\n", output)

    def _remove_list_items(
        self,
        source: str,
        command_span: tuple[int, int],
        matches: list[ReferenceOccurrence],
    ) -> str:
        start, end = command_span
        command_text = source[start:end]
        match = self._LIST.fullmatch(command_text)
        if match is None:
            return ""
        target_value = match.group("target")
        target_absolute_start = start + match.start("target")
        removed_spans = {
            (occurrence.target_start, occurrence.target_end)
            for occurrence in matches
        }
        kept: list[str] = []
        for item, item_start, item_end in self._split_list_targets(
            target_value,
            target_absolute_start,
        ):
            if (item_start, item_end) not in removed_spans:
                kept.append(item)
        if not kept:
            return ""
        relative_start, relative_end = match.span("target")
        return (
            command_text[:relative_start]
            + ",".join(kept)
            + command_text[relative_end:]
        )

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
        graphics = [
            item
            for item in self.occurrences(block, referring_file, False)
            if item.command == "includegraphics"
        ]
        if len(graphics) != 1:
            return None
        if self.match_candidate(
            graphics[0].raw_target,
            referring_file,
            target,
            target.suffix,
        ) is None:
            return None
        start = source.rfind("\n", 0, begin) + 1
        line_end = source.find("\n", block_end)
        return start, len(source) if line_end < 0 else line_end + 1
