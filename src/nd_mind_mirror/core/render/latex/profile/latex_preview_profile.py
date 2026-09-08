from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LatexPreviewProfile:
    key: str
    label: str
    template_path: Path


class LatexPreviewProfileRegistry:
    """Resolve the four supported LaTeX Preview wrapper profiles."""

    _LABELS = {
        "default": "Default",
        "graph": "Graph",
        "german": "German",
        "beamer": "Beamer",
    }

    def __init__(
        self,
        *,
        default_template_path: str | Path,
        graph_template_path: str | Path,
        german_template_path: str | Path,
        beamer_template_path: str | Path,
        active_profile: str = "default",
    ) -> None:
        self._templates = {
            "default": self._resolve(default_template_path),
            "graph": self._resolve(graph_template_path),
            "german": self._resolve(german_template_path),
            "beamer": self._resolve(beamer_template_path),
        }
        self._active_profile = self.normalize(active_profile)

    @classmethod
    def normalize(cls, value: str) -> str:
        key = str(value or "").strip().casefold()
        return key if key in cls._LABELS else "default"

    @classmethod
    def keys(cls) -> tuple[str, ...]:
        return tuple(cls._LABELS)

    @classmethod
    def label_for(cls, key: str) -> str:
        return cls._LABELS[cls.normalize(key)]

    @property
    def active_profile(self) -> str:
        return self._active_profile

    @property
    def active_template_path(self) -> Path:
        return self._templates[self._active_profile]

    def template_path(self, key: str) -> Path:
        return self._templates[self.normalize(key)]

    def profiles(self) -> tuple[LatexPreviewProfile, ...]:
        return tuple(
            LatexPreviewProfile(key, label, self._templates[key])
            for key, label in self._LABELS.items()
        )

    @staticmethod
    def _resolve(value: str | Path) -> Path:
        return Path(value).expanduser().resolve()
