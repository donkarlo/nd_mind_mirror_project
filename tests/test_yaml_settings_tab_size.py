from pathlib import Path

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings


def test_tab_size_is_shared_indent_size(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  tab_size: 6\n"
        "  indent_guides_enabled: true\n"
        "  indent_guide_color: '#cccccc'\n"
        "  indent_guide_width: 1.25\n",
        encoding="utf-8",
    )
    settings = YamlSettings(settings_path)

    assert settings.editor_tab_size == 6
    assert settings.editor_indent_size == 6
    assert settings.editor_indent_guides_enabled is True
    assert settings.editor_indent_guide_color == "#cccccc"
    assert settings.editor_indent_guide_width == 1.25
