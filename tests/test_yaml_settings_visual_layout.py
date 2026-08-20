from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings


def test_visual_layout_and_preview_highlight_settings(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n"
        "  source_padding_top: 7\n"
        "  source_padding_left: 8\n"
        "  source_padding_right: 9\n"
        "  visual_padding_top: 11\n"
        "  visual_padding_left: 12\n"
        "  visual_padding_right: 13\n"
        "  visual_update_debounce_ms: 190\n"
        "  visual_large_document_threshold_chars: 150000\n"
        "  visual_large_document_debounce_ms: 700\n"
        "preview:\n"
        "  edit_location_highlight_enabled: false\n"
        "  edit_location_highlight_debounce_ms: 260\n",
        encoding="utf-8",
    )
    settings = YamlSettings(settings_path)
    assert settings.editor_source_padding_top == 7
    assert settings.editor_source_padding_left == 8
    assert settings.editor_source_padding_right == 9
    assert settings.editor_visual_padding_top == 11
    assert settings.editor_visual_padding_left == 12
    assert settings.editor_visual_padding_right == 13
    assert settings.editor_visual_update_debounce_ms == 190
    assert settings.editor_visual_large_document_threshold_chars == 150000
    assert settings.editor_visual_large_document_debounce_ms == 700
    assert settings.preview_edit_location_highlight_enabled is False
    assert settings.preview_edit_location_highlight_debounce_ms == 260
