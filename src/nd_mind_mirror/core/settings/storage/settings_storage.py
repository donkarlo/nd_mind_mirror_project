from pathlib import Path
from typing import Any

from nd_mind_mirror.core.settings.storage.settings_storage_base import (
    SettingsStorage as BaseSettingsStorage,
)


class SettingsStorage(BaseSettingsStorage):
    """Persist Preview wrappers separately from user document templates."""

    def __init__(self, project_root: str | Path) -> None:
        super().__init__(project_root)
        self.graph_template_path = (
            self.templates_dir / "latex_preview_graph_template.tex"
        )
        self.german_template_path = (
            self.templates_dir / "latex_preview_german_template.tex"
        )
        self.article_document_template_path = (
            self.templates_dir / "latex_document_article_template.tex"
        )
        self.beamer_document_template_path = (
            self.templates_dir / "latex_document_beamer_template.tex"
        )

    def prepare(self) -> None:
        super().prepare()
        self._prepare_text(
            self.graph_template_path,
            self.defaults_root / "templates" / "latex_preview_graph_template.tex",
        )
        self._prepare_text(
            self.german_template_path,
            self.defaults_root / "templates" / "latex_preview_german_template.tex",
        )
        self._prepare_text(
            self.article_document_template_path,
            self.defaults_root / "templates" / "latex_document_article_template.tex",
        )
        self._prepare_text(
            self.beamer_document_template_path,
            self.defaults_root / "templates" / "latex_document_beamer_template.tex",
        )

    @classmethod
    def _normalize_settings(cls, data: Any) -> Any:
        result = BaseSettingsStorage._normalize_settings(data)
        if not isinstance(result, dict):
            return result

        preview = result.get("preview")
        if not isinstance(preview, dict):
            preview = {}
            result["preview"] = preview

        # Repair the accidental duplicate-key migration that could make the
        # Beamer path point at the German learning document template.
        if str(preview.get("latex_beamer_template_path", "")).strip() == (
            "templates/latex_german_learning_template.tex"
        ):
            preview["latex_beamer_template_path"] = (
                "templates/latex_preview_beamer_template.tex"
            )

        preview.setdefault("latex_profile", "default")
        preview.setdefault(
            "latex_graph_template_path",
            "templates/latex_preview_graph_template.tex",
        )
        preview.setdefault(
            "latex_german_template_path",
            "templates/latex_preview_german_template.tex",
        )

        new_file = result.get("new_latex_file")
        if not isinstance(new_file, dict):
            new_file = {}
            result["new_latex_file"] = new_file
        templates = new_file.get("templates")
        if not isinstance(templates, dict):
            templates = {}
            new_file["templates"] = templates

        # Only migrate the two shipped values that accidentally reused Preview
        # wrappers. Explicit custom document-template paths remain untouched.
        migrations = {
            "Article (standard)": (
                "templates/latex_preview_template.tex",
                "templates/latex_document_article_template.tex",
            ),
            "Beamer": (
                "templates/latex_preview_beamer_template.tex",
                "templates/latex_document_beamer_template.tex",
            ),
        }
        for label, (old_path, new_path) in migrations.items():
            if str(templates.get(label, "")).strip() == old_path:
                templates[label] = new_path

        return result
