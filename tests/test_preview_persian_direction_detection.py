from pathlib import Path

from nd_mind_mirror.core.latex.direction.latex_text_direction_resolver import (
    LatexTextDirectionResolver,
)
from nd_mind_mirror.core.render.latex.latex_preview_source_builder import (
    LatexPreviewSourceBuilder,
)


def _standalone_document(body: str) -> str:
    return (
        "\\documentclass[a4paper]{article}\n"
        "\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n"
    )


def test_arabic_combining_mark_is_not_a_strong_script_letter():
    assert not LatexTextDirectionResolver.contains_arabic_script_letters(
        "\u0651I want to buy a car in Graz."
    )


def test_real_persian_letters_are_detected():
    assert LatexTextDirectionResolver.contains_arabic_script_letters(
        "من یک ماشین می‌خواهم"
    )


def test_stray_shadda_does_not_enable_persian_main_language():
    builder = LatexPreviewSourceBuilder(Path("unused-template.tex"))
    prepared = builder.build(
        _standalone_document("\u0651I want to buy a car in Graz.")
    )
    assert "\\babelprovide[import,main]{persian}" not in prepared
    assert "% Preview-only Persian support" not in prepared


def test_persian_text_still_enables_persian_preview_support():
    builder = LatexPreviewSourceBuilder(Path("unused-template.tex"))
    prepared = builder.build(
        _standalone_document("من یک ماشین می‌خواهم")
    )
    assert "\\babelprovide[import,main]{persian}" in prepared
    assert "% Preview-only Persian support" in prepared
