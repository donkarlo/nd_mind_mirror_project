from nd_mind_mirror.core.latex.direction.latex_text_direction_resolver import (
    LatexTextDirectionResolver,
    TextDirection,
)


def test_structural_latex_lines_remain_ltr() -> None:
    resolver = LatexTextDirectionResolver()

    assert resolver.resolve(r"\section{مقدمه}") == TextDirection.LEFT_TO_RIGHT
    assert resolver.resolve(r"\begin{frame}{عنوان فارسی}") == TextDirection.LEFT_TO_RIGHT


def test_persian_prose_is_rtl() -> None:
    resolver = LatexTextDirectionResolver()

    assert resolver.resolve("این یک متن فارسی است.") == TextDirection.RIGHT_TO_LEFT


def test_mixed_persian_english_prose_is_rtl() -> None:
    resolver = LatexTextDirectionResolver()

    assert resolver.resolve(
        "این مدل از Transformer برای پیش‌بینی استفاده می‌کند."
    ) == TextDirection.RIGHT_TO_LEFT


def test_long_citation_key_does_not_dominate_language_detection() -> None:
    resolver = LatexTextDirectionResolver()

    assert resolver.resolve(
        r"\cite{a-very-long-english-citation-key-2026} متن فارسی کوتاه است."
    ) == TextDirection.RIGHT_TO_LEFT


def test_english_prose_is_ltr() -> None:
    resolver = LatexTextDirectionResolver()

    assert resolver.resolve(
        "Transformer model predicts the sequence."
    ) == TextDirection.LEFT_TO_RIGHT
