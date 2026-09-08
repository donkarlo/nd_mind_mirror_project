"""Regression checks that new documents never reuse internal Preview wrappers."""

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = PROJECT_ROOT / "src/nd_mind_mirror/core/settings/defaults"
DEFAULT_SETTINGS = DEFAULTS / "settings.yaml"
ARTICLE_DOCUMENT = DEFAULTS / "templates/latex_document_article_template.tex"
BEAMER_DOCUMENT = DEFAULTS / "templates/latex_document_beamer_template.tex"
ARTICLE_PREVIEW = DEFAULTS / "templates/latex_preview_template.tex"
STORAGE = PROJECT_ROOT / "src/nd_mind_mirror/core/settings/storage/settings_storage.py"
YAML_SETTINGS = PROJECT_ROOT / "src/nd_mind_mirror/core/settings/yaml/yaml_settings.py"


def test_new_file_defaults_use_document_templates() -> None:
    data = yaml.safe_load(DEFAULT_SETTINGS.read_text(encoding="utf-8"))
    templates = data["new_latex_file"]["templates"]
    assert templates["Article (standard)"] == (
        "templates/latex_document_article_template.tex"
    )
    assert templates["Beamer"] == "templates/latex_document_beamer_template.tex"


def test_document_templates_do_not_contain_preview_contract() -> None:
    for path in (ARTICLE_DOCUMENT, BEAMER_DOCUMENT):
        source = path.read_text(encoding="utf-8")
        assert "\\usepackage[active,tightpage]{preview}" not in source
        assert "\\PreviewBorder" not in source
        assert "\\begin{preview}" not in source
        assert "ND_MIND_MIRROR_CONTENT" not in source


def test_preview_wrapper_keeps_tight_page_behavior() -> None:
    source = ARTICLE_PREVIEW.read_text(encoding="utf-8")
    assert "\\usepackage[active,tightpage]{preview}" in source
    assert "\\begin{preview}" in source
    assert "ND_MIND_MIRROR_CONTENT" in source


def test_migration_only_targets_old_shipped_preview_paths() -> None:
    source = STORAGE.read_text(encoding="utf-8")
    assert '"templates/latex_preview_template.tex"' in source
    assert '"templates/latex_document_article_template.tex"' in source
    assert '"templates/latex_preview_beamer_template.tex"' in source
    assert '"templates/latex_document_beamer_template.tex"' in source
    assert "Explicit custom document-template paths remain untouched" in source


def test_yaml_settings_fallback_uses_document_templates() -> None:
    source = YAML_SETTINGS.read_text(encoding="utf-8")
    assert "latex_document_article_template.tex" in source
    assert "latex_document_beamer_template.tex" in source
    fallback = source.split("if result:", 1)[1]
    assert "latex_preview_template.tex" not in fallback
    assert "latex_preview_beamer_template.tex" not in fallback
