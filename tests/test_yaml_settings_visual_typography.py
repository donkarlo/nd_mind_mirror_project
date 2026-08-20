from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings


def test_visual_typography_can_be_configured_independently(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  font_size: 16\n"
        "  visual_font_size: 19\n"
        "  line_height_percent: 200\n"
        "  visual_line_height_percent: 135\n",
        encoding="utf-8",
    )

    settings = YamlSettings(settings_path)

    assert settings.editor_font_size == 16
    assert settings.editor_visual_font_size == 19
    assert settings.editor_line_height_percent == 200
    assert settings.editor_visual_line_height_percent == 135


def test_visual_typography_falls_back_to_source_values(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  font_size: 17\n"
        "  line_height_percent: 180\n",
        encoding="utf-8",
    )

    settings = YamlSettings(settings_path)

    assert settings.editor_visual_font_size == 17
    assert settings.editor_visual_line_height_percent == 180
