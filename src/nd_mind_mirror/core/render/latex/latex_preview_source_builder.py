from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_preview_source_builder_base import (
    LatexPreviewSourceBuilder as BaseLatexPreviewSourceBuilder,
)
from nd_mind_mirror.core.render.latex.profile.latex_preview_profile import (
    LatexPreviewProfileRegistry,
)


class LatexPreviewSourceBuilder(BaseLatexPreviewSourceBuilder):
    """Choose a Preview wrapper from the configured four-profile registry."""

    def __init__(
        self,
        template_path: str | Path,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        super().__init__(
            template_path,
            beamer_template_path=beamer_template_path,
        )
        self._graph_template_path: Path | None = None
        self._german_template_path: Path | None = None
        self._active_preview_profile = "default"

    @property
    def active_preview_profile(self) -> str:
        return self._active_preview_profile

    def configure_profiles(
        self,
        *,
        active_profile: str,
        default_template_path: str | Path,
        graph_template_path: str | Path,
        german_template_path: str | Path,
        beamer_template_path: str | Path,
    ) -> None:
        self.set_template_path(default_template_path)
        self.set_beamer_template_path(beamer_template_path)
        self._graph_template_path = self._resolve_profile_path(graph_template_path)
        self._german_template_path = self._resolve_profile_path(german_template_path)
        self._active_preview_profile = LatexPreviewProfileRegistry.normalize(
            active_profile
        )

    def _template_for_source(self, source: str) -> Path:
        profile = self._active_preview_profile
        if profile == "graph" and self._graph_template_path is not None:
            return self._graph_template_path
        if profile == "german" and self._german_template_path is not None:
            return self._german_template_path
        if profile == "beamer" and self._beamer_template_path is not None:
            return self._beamer_template_path

        # Default keeps the existing intelligent Beamer fragment detection.
        return super()._template_for_source(source)

    @staticmethod
    def _resolve_profile_path(value: str | Path) -> Path:
        return Path(value).expanduser().resolve()
