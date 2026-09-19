"""Rewrite workspace file references after one or more paths move."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


class PathReferenceUpdater:
    """Rewrite supported local references while preserving their path style."""

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
    _MAX_FILE_SIZE = 8 * 1024 * 1024

    _LATEX_COMMAND_PATTERN = re.compile(
        r"(?P<prefix>\\(?P<command>"
        r"input|include|subfile|includegraphics|includepdf|addbibresource|"
        r"bibliography|lstinputlisting|verbatiminput|VerbatimInput|"
        r"includeonly|href|url"
        r")\*?(?:\s*\[[^\]\n]*\])?\s*\{)"
        r"(?P<value>[^{}\n]+)"
        r"(?P<suffix>\})"
    )
    _INPUTMINTED_PATTERN = re.compile(
        r"(?P<prefix>\\inputminted(?:\s*\[[^\]\n]*\])?\s*"
        r"\{[^{}\n]+\}\s*\{)"
        r"(?P<value>[^{}\n]+)"
        r"(?P<suffix>\})"
    )
    _MARKDOWN_LINK_PATTERN = re.compile(
        r"(?P<prefix>!?\[[^\]\n]*\]\()(?P<value>[^)\n]+)(?P<suffix>\))"
    )
    _HTML_REFERENCE_PATTERN = re.compile(
        r"(?P<prefix>\b(?:src|href)\s*=\s*(?P<quote>['\"]))"
        r"(?P<value>[^'\"\n]+)(?P<suffix>(?P=quote))",
        re.IGNORECASE,
    )

    @classmethod
    def update_workspace_references(
        cls,
        workspace_root: str | Path,
        old_path: str | Path,
        new_path: str | Path,
        ignore_file_path: str | Path | None = None,
    ) -> list[Path]:
        """Rewrite one moved path across the workspace."""
        return cls.update_workspace_reference_mappings(
            workspace_root,
            [(old_path, new_path)],
            ignore_file_path=ignore_file_path,
        )

    @classmethod
    def update_workspace_reference_mappings(
        cls,
        workspace_root: str | Path,
        mappings: Sequence[tuple[str | Path, str | Path]],
        ignore_file_path: str | Path | None = None,
        exclude_files: Iterable[str | Path] = (),
    ) -> list[Path]:
        """Rewrite many moved paths in one workspace scan."""
        root = Path(workspace_root).expanduser().resolve()
        normalized = cls._normalize_mappings(mappings)
        if not root.is_dir() or not normalized:
            return []

        excluded = {
            Path(path).expanduser().resolve(strict=False)
            for path in exclude_files
        }
        matcher = SearchIgnoreMatcher.from_file(ignore_file_path)
        changed: list[Path] = []

        for directory, dirnames, filenames in os.walk(root):
            directory_path = Path(directory)
            kept_directories: list[str] = []
            for name in dirnames:
                child = directory_path / name
                if name in cls._SKIP_DIRECTORIES:
                    continue
                if matcher.is_ignored(child, root, is_directory=True):
                    continue
                kept_directories.append(name)
            dirnames[:] = kept_directories

            for name in filenames:
                candidate = directory_path / name
                if candidate.suffix.lower() not in cls._TEXT_SUFFIXES:
                    continue
                resolved_candidate = candidate.resolve(strict=False)
                if resolved_candidate in excluded:
                    continue
                if matcher.is_ignored(candidate, root, is_directory=False):
                    continue
                try:
                    if candidate.stat().st_size > cls._MAX_FILE_SIZE:
                        continue
                    source = candidate.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue

                updated = cls.rewrite_source_for_mappings(
                    source,
                    referring_file=candidate,
                    workspace_root=root,
                    mappings=normalized,
                )
                if updated == source:
                    continue
                try:
                    cls._write_text_atomic(candidate, updated)
                except OSError:
                    continue
                changed.append(resolved_candidate)

        return changed

    @classmethod
    def rewrite_source_for_mappings(
        cls,
        source: str,
        *,
        referring_file: str | Path,
        workspace_root: str | Path,
        mappings: Sequence[tuple[str | Path, str | Path]],
    ) -> str:
        """Rewrite path mappings in one source string without touching the filesystem."""
        referring = Path(referring_file).expanduser().resolve(strict=False)
        root = Path(workspace_root).expanduser().resolve(strict=False)
        updated = source
        for old_path, new_path in cls._normalize_mappings(mappings):
            updated = cls._rewrite_for_file(
                updated,
                referring_file=referring,
                workspace_root=root,
                old_path=old_path,
                new_path=new_path,
            )
        return updated

    @classmethod
    def _normalize_mappings(
        cls,
        mappings: Sequence[tuple[str | Path, str | Path]],
    ) -> list[tuple[Path, Path]]:
        normalized: list[tuple[Path, Path]] = []
        seen: set[tuple[Path, Path]] = set()
        for old_path, new_path in mappings:
            old = Path(old_path).expanduser().resolve(strict=False)
            new = Path(new_path).expanduser().resolve(strict=False)
            pair = (old, new)
            if old == new or pair in seen:
                continue
            seen.add(pair)
            normalized.append(pair)
        return normalized

    @classmethod
    def _rewrite_for_file(
        cls,
        source: str,
        *,
        referring_file: Path,
        workspace_root: Path,
        old_path: Path,
        new_path: Path,
    ) -> str:
        resolver = WorkspaceReferenceResolver(workspace_root)

        def replace_reference(match: re.Match[str]) -> str:
            command = match.groupdict().get("command") or ""
            value = match.group("value")
            rewritten = cls._rewrite_reference_value(
                value,
                command=command,
                referring_file=referring_file,
                resolver=resolver,
                old_path=old_path,
                new_path=new_path,
                allow_list=command in {"bibliography", "includeonly"},
            )
            return f"{match.group('prefix')}{rewritten}{match.group('suffix')}"

        updated = cls._LATEX_COMMAND_PATTERN.sub(replace_reference, source)
        updated = cls._INPUTMINTED_PATTERN.sub(replace_reference, updated)

        if referring_file.suffix.lower() in {".md", ".markdown"}:
            updated = cls._MARKDOWN_LINK_PATTERN.sub(replace_reference, updated)

        if referring_file.suffix.lower() in {".html", ".htm"}:
            updated = cls._HTML_REFERENCE_PATTERN.sub(replace_reference, updated)

        return updated

    @classmethod
    def _rewrite_reference_value(
        cls,
        value: str,
        *,
        command: str,
        referring_file: Path,
        resolver: WorkspaceReferenceResolver,
        old_path: Path,
        new_path: Path,
        allow_list: bool = False,
    ) -> str:
        if allow_list and "," in value:
            parts = value.split(",")
            return ",".join(
                cls._rewrite_reference_value(
                    part,
                    command=command,
                    referring_file=referring_file,
                    resolver=resolver,
                    old_path=old_path,
                    new_path=new_path,
                    allow_list=False,
                )
                for part in parts
            )

        leading = value[: len(value) - len(value.lstrip())]
        trailing = value[len(value.rstrip()) :]
        token = value.strip()
        if not token:
            return value

        lowered = token.casefold()
        if not resolver.is_local_reference(token):
            return value

        file_url_prefix = ""
        if lowered.startswith("file://"):
            file_url_prefix = token[:7]
            token = token[7:]
        elif lowered.startswith("file:"):
            file_url_prefix = token[:5]
            token = token[5:]

        tex_escaped_underscore = r"\_" in token
        path_token = token.replace(r"\_", "_")
        original_dot_prefix = path_token.startswith("./")

        match = resolver.match_candidate(
            path_token,
            referring_file,
            old_path,
            suffix_hint=old_path.suffix if old_path.suffix else "",
        )
        if match is None:
            return value

        base_kind, matched_path, omitted_suffix = match
        mapped = cls._map_old_to_new(matched_path, old_path, new_path)
        if mapped is None:
            return value

        output = resolver.format_path(mapped, base_kind, referring_file)
        if output is None:
            return value

        if omitted_suffix and mapped.suffix and output.endswith(mapped.suffix):
            output = output[: -len(mapped.suffix)]

        if original_dot_prefix and not output.startswith(("./", "../", "/")):
            output = "./" + output
        if tex_escaped_underscore:
            output = output.replace("_", r"\_")

        return f"{leading}{file_url_prefix}{output}{trailing}"

    @staticmethod
    def _map_old_to_new(
        candidate: Path,
        old_path: Path,
        new_path: Path,
    ) -> Path | None:
        if candidate == old_path:
            return new_path
        try:
            relative = candidate.relative_to(old_path)
        except ValueError:
            return None
        return new_path / relative

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.nd_reference.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, path)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
