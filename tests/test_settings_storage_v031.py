from pathlib import Path

import yaml

from nd_mind_mirror.core.settings.storage.settings_storage import SettingsStorage
from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings


def test_external_settings_migrate_and_merge_without_losing_user_values(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "settings.yaml").write_text(
        "editor:\n  font_size: 23\nsearch:\n  default_path: /custom/workspace\n",
        encoding="utf-8",
    )
    data_root = tmp_path / "data" / "nd_mind_mirror_project"
    monkeypatch.setattr(SettingsStorage, "DATA_ROOT", data_root)

    storage = SettingsStorage(project)
    storage.prepare()

    data = yaml.safe_load(storage.settings_path.read_text(encoding="utf-8"))
    assert data["editor"]["source_font_size"] == 23
    assert data["search"]["default_path"] == "/custom/workspace"
    assert "preview" in data
    assert data["new_latex_file"]["templates"]["Beamer"].endswith(
        "latex_preview_beamer_template.tex"
    )
    assert storage.article_template_path.is_file()
    assert storage.beamer_template_path.is_file()


def test_source_font_size_has_explicit_key_and_legacy_fallback(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("editor:\n  source_font_size: 27\n  visual_font_size: 19\n", encoding="utf-8")
    settings = YamlSettings(path)
    assert settings.editor_source_font_size == 27
    assert settings.editor_font_size == 27
    assert settings.editor_visual_font_size == 19
