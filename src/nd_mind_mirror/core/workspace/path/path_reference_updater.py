from __future__ import annotations

import os
from pathlib import Path

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher


class PathReferenceUpdater:
    """Rewrite textual references after a file or folder is moved in a workspace."""

    _TEXT_SUFFIXES = {
        ".tex",
        ".bib",
        ".yaml",
        ".yml",
        ".md",
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

    @classmethod
    def update_workspace_references(
        cls,
        workspace_root: str | Path,
        old_path: str | Path,
        new_path: str | Path,
        ignore_file_path: str | Path | None = None,
    ) -> list[Path]:
        root = Path(workspace_root).expanduser().resolve()
        old = Path(old_path).expanduser().resolve()
        new = Path(new_path).expanduser().resolve()
        if not root.is_dir() or old == new:
            return []

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
                if matcher.is_ignored(candidate, root, is_directory=False):
                    continue
                try:
                    if candidate.stat().st_size > cls._MAX_FILE_SIZE:
                        continue
                    source = candidate.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue

                updated = cls._rewrite_for_file(
                    source,
                    referring_file=candidate,
                    workspace_root=root,
                    old_path=old,
                    new_path=new,
                )
                if updated == source:
                    continue
                try:
                    candidate.write_text(updated, encoding="utf-8")
                except OSError:
                    continue
                changed.append(candidate.resolve())
        return changed

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
        pairs: list[tuple[str, str]] = []

        def add(old_value: str, new_value: str) -> None:
            old_value = old_value.replace(os.sep, "/")
            new_value = new_value.replace(os.sep, "/")
            if not old_value or old_value == new_value:
                return
            pair = (old_value, new_value)
            if pair not in pairs:
                pairs.append(pair)

        add(str(old_path), str(new_path))

        try:
            add(
                old_path.relative_to(workspace_root).as_posix(),
                new_path.relative_to(workspace_root).as_posix(),
            )
        except ValueError:
            pass

        try:
            old_relative = os.path.relpath(old_path, referring_file.parent)
            new_relative = os.path.relpath(new_path, referring_file.parent)
            add(old_relative, new_relative)
            if not old_relative.startswith("."):
                add(f"./{old_relative}", f"./{new_relative}")
        except (OSError, ValueError):
            pass

        # LaTeX commonly omits the .tex suffix in \input and \include.
        if old_path.suffix.lower() == ".tex" and new_path.suffix.lower() == ".tex":
            suffix_pairs = list(pairs)
            for old_value, new_value in suffix_pairs:
                if old_value.endswith(".tex") and new_value.endswith(".tex"):
                    add(old_value[:-4], new_value[:-4])

        # Longest paths first so a full absolute path is rewritten before a
        # shorter workspace-relative fragment that may be contained inside it.
        updated = source
        for old_value, new_value in sorted(pairs, key=lambda item: len(item[0]), reverse=True):
            updated = updated.replace(old_value, new_value)
        return updated
