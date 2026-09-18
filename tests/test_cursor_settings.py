from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings


def test_cursor_appearance_settings_are_exposed(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  cursor_color: '#123456'\n"
        "  cursor_size_percent: 135\n"
        "  cursor_thickness: 4\n",
        encoding="utf-8",
    )

    settings = YamlSettings(settings_path)

    assert settings.editor_cursor_color == "#123456"
    assert settings.editor_cursor_size_percent == 135
    assert settings.editor_cursor_thickness == 4
    assert settings.editor_cursor_width == 4


def test_cursor_thickness_falls_back_to_legacy_width(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  cursor_width: 5\n",
        encoding="utf-8",
    )

    settings = YamlSettings(settings_path)

    assert settings.editor_cursor_thickness == 5
    assert settings.editor_cursor_width == 5
