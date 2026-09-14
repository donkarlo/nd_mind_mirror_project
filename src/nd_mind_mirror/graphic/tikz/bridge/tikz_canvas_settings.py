"""Load and materialize TikZ iPad canvas dimensions from Mind Mirror settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


@dataclass(frozen=True)
class TikZCanvasSettings:
    """Logical iPad canvas dimensions carried as source metadata."""

    width: int = 760
    height: int = 980

    _MARKER = re.compile(
        r"^%\s*nd_mind_mirror_canvas\s*:\s*(\d+)\s*x\s*(\d+)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    @classmethod
    def load(cls, workspace: str | Path) -> "TikZCanvasSettings":
        settings_path = (
            Path(workspace).expanduser().resolve()
            / "data"
            / "nd_mind_mirror_project"
            / "settings.yaml"
        )
        try:
            data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
            graphic = data.get("graphic", {}) if isinstance(data, dict) else {}
            tikz = graphic.get("tikz", {}) if isinstance(graphic, dict) else {}
            width = cls._dimension(tikz.get("canvas_width"), 760)
            height = cls._dimension(tikz.get("canvas_height"), 980)
            return cls(width=width, height=height)
        except (OSError, yaml.YAMLError, AttributeError):
            return cls()

    def materialize_source(self, source: str) -> str:
        """Preserve per-file metadata, otherwise inject current configured defaults."""
        if self._MARKER.search(source):
            return source
        marker = f"% nd_mind_mirror_canvas: {self.width}x{self.height}\n"
        return marker + source

    @staticmethod
    def _dimension(value: object, default: int) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = default
        return max(result, 64)
