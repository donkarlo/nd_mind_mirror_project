from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Iterable

import yaml


class SearchIgnoreMatcher:
    def __init__(self, patterns: Iterable[str] = ()) -> None:
        self._patterns = [
            str(pattern).strip()
            for pattern in patterns
            if str(pattern).strip()
            and not str(pattern).lstrip().startswith("#")
        ]

    @property
    def patterns(self) -> list[str]:
        return list(self._patterns)

    @classmethod
    def from_file(
        cls,
        path: str | Path | None,
    ) -> "SearchIgnoreMatcher":
        if path is None:
            return cls()

        file_path = Path(path).expanduser()

        try:
            loaded = yaml.safe_load(
                file_path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError):
            return cls()

        if isinstance(loaded, list):
            patterns = loaded
        elif isinstance(loaded, dict):
            patterns = loaded.get("ignore", [])
        else:
            patterns = []

        if not isinstance(patterns, list):
            patterns = []

        return cls(patterns)

    def is_ignored(
        self,
        path: str | Path,
        root_path: str | Path,
        is_directory: bool,
    ) -> bool:
        candidate = Path(path)
        root = Path(root_path)

        try:
            relative = candidate.relative_to(root)
        except ValueError:
            return True

        relative_text = relative.as_posix().strip("/")
        if not relative_text:
            return False

        ignored = False

        for raw_rule in self._patterns:
            negated = raw_rule.startswith("!")
            rule = raw_rule[1:] if negated else raw_rule
            rule = rule.strip()

            if not rule:
                continue

            if self._matches_rule(
                relative_text=relative_text,
                basename=candidate.name,
                is_directory=is_directory,
                rule=rule,
            ):
                ignored = not negated

        return ignored

    def _matches_rule(
        self,
        relative_text: str,
        basename: str,
        is_directory: bool,
        rule: str,
    ) -> bool:
        anchored = rule.startswith("/")
        if anchored:
            rule = rule[1:]

        directory_only = rule.endswith("/")
        if directory_only:
            rule = rule.rstrip("/")

        if directory_only and not is_directory:
            return False

        if not rule:
            return False

        normalized_rule = rule.replace("\\", "/")
        relative = PurePosixPath(relative_text)

        if anchored:
            return fnmatchcase(
                relative_text,
                normalized_rule,
            )

        if "/" not in normalized_rule:
            if fnmatchcase(basename, normalized_rule):
                return True

            if directory_only:
                return any(
                    fnmatchcase(part, normalized_rule)
                    for part in relative.parts
                )

            return False

        if relative.match(normalized_rule):
            return True

        if normalized_rule.startswith("**/"):
            shortened = normalized_rule[3:]
            if relative.match(shortened):
                return True

        return fnmatchcase(
            relative_text,
            normalized_rule,
        )
