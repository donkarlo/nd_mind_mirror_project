from pathlib import Path

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings


def test_preview_profile_paths_are_independent(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "preview:\n"
        "  latex_profile: german\n"
        "  latex_template_path: templates/default.tex\n"
        "  latex_graph_template_path: templates/graph.tex\n"
        "  latex_german_template_path: templates/german.tex\n"
        "  latex_beamer_template_path: templates/beamer.tex\n",
        encoding="utf-8",
    )

    settings = YamlSettings(settings_path)
    assert settings.preview_latex_profile == "german"
    assert settings.preview_latex_graph_template_path == (
        tmp_path / "templates" / "graph.tex"
    ).resolve()
    assert settings.preview_latex_german_template_path == (
        tmp_path / "templates" / "german.tex"
    ).resolve()
    assert settings.preview_latex_beamer_template_path == (
        tmp_path / "templates" / "beamer.tex"
    ).resolve()
