from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LatexShortcut:
    trigger: str
    replacement: str
    description: str = ""


class LatexShortcutProvider:
    """Load user-editable LaTeX text shortcuts from YAML."""

    CURSOR_MARKER = "{{cursor}}"

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[LatexShortcut]:
        try:
            raw = yaml.safe_load(
                self._path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError):
            return []

        if not isinstance(raw, dict):
            return []

        entries = raw.get("shortcuts", raw)
        if not isinstance(entries, dict):
            return []

        result: list[LatexShortcut] = []

        for trigger, value in entries.items():
            normalized_trigger = str(trigger).strip()
            if not normalized_trigger:
                continue

            replacement = ""
            description = ""

            if isinstance(value, str):
                replacement = value
            elif isinstance(value, dict):
                replacement = str(
                    value.get(
                        "replacement",
                        value.get("text", ""),
                    )
                )
                description = str(
                    value.get("description", "")
                ).strip()
            else:
                continue

            if not replacement:
                continue

            result.append(
                LatexShortcut(
                    trigger=normalized_trigger,
                    replacement=replacement,
                    description=description,
                )
            )

        return sorted(
            result,
            key=lambda item: item.trigger.casefold(),
        )
