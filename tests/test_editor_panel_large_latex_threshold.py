from pathlib import Path


def test_editor_panel_uses_configured_large_source_threshold() -> None:
    project_root = Path(__file__).resolve().parents[1]
    panel_source = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "panel"
        / "editor"
        / "editor_panel.py"
    ).read_text(encoding="utf-8")

    assert "editor_source_large_document_threshold_chars" in panel_source
    assert "if len(content) >= large_document_threshold" in panel_source
    assert "_SOURCE_VIRTUALIZATION_THRESHOLD_CHARS = 1_000_000" not in panel_source


def test_default_large_source_threshold_remains_120k() -> None:
    project_root = Path(__file__).resolve().parents[1]
    settings_source = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "core"
        / "settings"
        / "defaults"
        / "settings.yaml"
    ).read_text(encoding="utf-8")

    assert "source_large_document_threshold_chars: 120000" in settings_source
