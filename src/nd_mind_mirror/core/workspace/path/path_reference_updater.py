from __future__ import annotations

import os
import re
from pathlib import Path

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher


class PathReferenceUpdater:
    """Rewrite real file references after a file or folder is moved."""

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
        def replace_reference(match: re.Match[str]) -> str:
            command = match.groupdict().get("command") or ""
            value = match.group("value")
            rewritten = cls._rewrite_reference_value(
                value,
                referring_file=referring_file,
                workspace_root=workspace_root,
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
        referring_file: Path,
        workspace_root: Path,
        old_path: Path,
        new_path: Path,
        allow_list: bool = False,
    ) -> str:
        if allow_list and "," in value:
            parts = value.split(",")
            return ",".join(
                cls._rewrite_reference_value(
                    part,
                    referring_file=referring_file,
                    workspace_root=workspace_root,
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
        if lowered.startswith(("http://", "https://", "mailto:", "data:", "ftp://", "#")):
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

        match = cls._match_reference_path(
            path_token,
            referring_file=referring_file,
            workspace_root=workspace_root,
            old_path=old_path,
        )
        if match is None:
            return value

        base_kind, matched_path, omitted_suffix = match
        mapped = cls._map_old_to_new(matched_path, old_path, new_path)
        if mapped is None:
            return value

        if base_kind == "absolute":
            output = mapped.as_posix()
        elif base_kind == "file_relative":
            output = os.path.relpath(mapped, referring_file.parent).replace(os.sep, "/")
        else:
            try:
                output = mapped.relative_to(workspace_root).as_posix()
            except ValueError:
                return value

        if omitted_suffix and new_path.is_file() and mapped == new_path:
            suffix = new_path.suffix
            if suffix and output.endswith(suffix):
                output = output[: -len(suffix)]

        if original_dot_prefix and not output.startswith(("./", "../", "/")):
            output = "./" + output
        if tex_escaped_underscore:
            output = output.replace("_", r"\_")

        return f"{leading}{file_url_prefix}{output}{trailing}"

    @classmethod
    def _match_reference_path(
        cls,
        token: str,
        *,
        referring_file: Path,
        workspace_root: Path,
        old_path: Path,
    ) -> tuple[str, Path, bool] | None:
        raw_path = Path(token).expanduser()
        if raw_path.is_absolute():
            candidates = [("absolute", raw_path)]
        else:
            candidates = [
                ("file_relative", referring_file.parent / raw_path),
                ("workspace_relative", workspace_root / raw_path),
            ]

        for kind, candidate in candidates:
            resolved = cls._resolve_without_requirement(candidate)
            if cls._is_same_or_child(resolved, old_path):
                return kind, resolved, False

            if old_path.suffix and not Path(token).suffix:
                with_suffix = cls._resolve_without_requirement(
                    candidate.with_suffix(old_path.suffix)
                )
                if cls._is_same_or_child(with_suffix, old_path):
                    return kind, with_suffix, True

        return None

    @staticmethod
    def _resolve_without_requirement(path: Path) -> Path:
        try:
            return path.resolve(strict=False)
        except OSError:
            return Path(os.path.abspath(os.fspath(path)))

    @staticmethod
    def _is_same_or_child(candidate: Path, root: Path) -> bool:
        if candidate == root:
            return True
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _map_old_to_new(candidate: Path, old_path: Path, new_path: Path) -> Path | None:
        if candidate == old_path:
            return new_path
        try:
            relative = candidate.relative_to(old_path)
        except ValueError:
            return None
        return new_path / relative
