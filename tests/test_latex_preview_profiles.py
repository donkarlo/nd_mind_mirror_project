from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_preview_source_builder import (
    LatexPreviewSourceBuilder,
)
from nd_mind_mirror.core.render.latex.profile.latex_preview_profile import (
    LatexPreviewProfileRegistry,
)


def _templates(tmp_path: Path) -> dict[str, Path]:
    result = {}
    for key in LatexPreviewProfileRegistry.keys():
        path = tmp_path / f"{key}.tex"
        path.write_text(
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "% ND_MIND_MIRROR_CONTENT\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        result[key] = path
    return result


def test_explicit_preview_profiles_select_their_own_templates(tmp_path: Path) -> None:
    templates = _templates(tmp_path)
    builder = LatexPreviewSourceBuilder(
        templates["default"],
        beamer_template_path=templates["beamer"],
    )

    for profile in ("graph", "german", "beamer"):
        builder.configure_profiles(
            active_profile=profile,
            default_template_path=templates["default"],
            graph_template_path=templates["graph"],
            german_template_path=templates["german"],
            beamer_template_path=templates["beamer"],
        )
        assert builder._template_for_source("plain fragment") == templates[profile]


def test_default_profile_keeps_automatic_beamer_fragment_detection(tmp_path: Path) -> None:
    templates = _templates(tmp_path)
    builder = LatexPreviewSourceBuilder(
        templates["default"],
        beamer_template_path=templates["beamer"],
    )
    builder.configure_profiles(
        active_profile="default",
        default_template_path=templates["default"],
        graph_template_path=templates["graph"],
        german_template_path=templates["german"],
        beamer_template_path=templates["beamer"],
    )

    assert builder._template_for_source("\\begin{frame}{X}x\\end{frame}") == templates["beamer"]
    assert builder._template_for_source("ordinary text") == templates["default"]
