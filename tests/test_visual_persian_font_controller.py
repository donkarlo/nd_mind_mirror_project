"""Regression tests for configurable Persian font handling in LaTeX Visual mode."""

from nd_mind_mirror.ui.window.main.visual_persian_font_controller import (
    VisualPersianFontController,
)


def test_visual_persian_font_defaults_to_noto_naskh_arabic(tmp_path):
    """Missing settings keep the requested Noto Naskh Arabic default."""
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text("editor:\n  font_family: DejaVu Sans Mono\n", encoding="utf-8")

    assert (
        VisualPersianFontController._read_visual_persian_font_family(settings_path)
        == "Noto Naskh Arabic"
    )


def test_visual_persian_font_can_be_overridden(tmp_path):
    """The merged settings file can independently override the Visual Persian family."""
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        "editor:\n  visual_persian_font_family: Vazirmatn\n",
        encoding="utf-8",
    )

    assert (
        VisualPersianFontController._read_visual_persian_font_family(settings_path)
        == "Vazirmatn"
    )


def test_arabic_script_detector_covers_persian_and_excludes_latin():
    """Persian letters and ZWNJ are targeted while ordinary Latin text is not."""
    detect = VisualPersianFontController._is_arabic_script_character

    assert detect("ف")
    assert detect("ی")
    assert detect("‌")
    assert not detect("A")
