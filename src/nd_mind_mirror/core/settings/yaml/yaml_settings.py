from pathlib import Path

from nd_mind_mirror.core.render.latex.profile.latex_preview_profile import (
    LatexPreviewProfileRegistry,
)
from nd_mind_mirror.core.settings.yaml.yaml_settings_base import (
    YamlSettings as BaseYamlSettings,
)


class YamlSettings(BaseYamlSettings):
    """Expose Preview profiles, TikZ canvas defaults, and document templates."""

    @property
    def preview_latex_profile(self) -> str:
        return LatexPreviewProfileRegistry.normalize(
            str(self._get("preview", "latex_profile", default="default"))
        )

    @property
    def preview_latex_graph_template_path(self) -> Path:
        return self._preview_profile_template_path(
            "latex_graph_template_path",
            "templates/latex_preview_graph_template.tex",
        )

    @property
    def preview_latex_german_template_path(self) -> Path:
        return self._preview_profile_template_path(
            "latex_german_template_path",
            "templates/latex_preview_german_template.tex",
        )

    @property
    def graphic_tikz_canvas_width(self) -> int:
        return self._tikz_canvas_dimension("canvas_width", 760)

    @property
    def graphic_tikz_canvas_height(self) -> int:
        return self._tikz_canvas_dimension("canvas_height", 980)

    @property
    def new_latex_file_templates(self) -> list[tuple[str, Path]]:
        """Return user document templates without falling back to Preview wrappers."""
        section = self._data.get("new_latex_file", {})
        raw_templates = section.get("templates", {}) if isinstance(section, dict) else {}
        result: list[tuple[str, Path]] = []
        if isinstance(raw_templates, dict):
            for label, raw_path in raw_templates.items():
                label_text = str(label).strip()
                path_text = str(raw_path).strip()
                if not label_text or not path_text:
                    continue
                result.append(
                    (label_text, self._resolve_settings_relative_path(path_text))
                )
        if result:
            return result
        return [
            (
                "Article (standard)",
                self._resolve_settings_relative_path(
                    "templates/latex_document_article_template.tex"
                ),
            ),
            (
                "Beamer",
                self._resolve_settings_relative_path(
                    "templates/latex_document_beamer_template.tex"
                ),
            ),
        ]

    def preview_latex_profile_registry(self) -> LatexPreviewProfileRegistry:
        return LatexPreviewProfileRegistry(
            default_template_path=self.preview_latex_template_path,
            graph_template_path=self.preview_latex_graph_template_path,
            german_template_path=self.preview_latex_german_template_path,
            beamer_template_path=self.preview_latex_beamer_template_path,
            active_profile=self.preview_latex_profile,
        )

    def _preview_profile_template_path(self, key: str, default: str) -> Path:
        raw = str(self._get("preview", key, default=default)).strip()
        return self._resolve_settings_relative_path(raw or default)

    def _resolve_settings_relative_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = self._settings_path.parent / candidate
        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

    def _tikz_canvas_dimension(self, key: str, default: int) -> int:
        graphic = self._data.get("graphic", {})
        tikz = graphic.get("tikz", {}) if isinstance(graphic, dict) else {}
        raw = tikz.get(key, default) if isinstance(tikz, dict) else default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return max(value, 64)
