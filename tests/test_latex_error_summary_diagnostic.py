from nd_mind_mirror.core.render.latex.diagnostic.latex_compiler_diagnostic_extractor import (
    LatexCompilerDiagnosticExtractor,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_severity_classifier import (
    LatexDiagnosticSeverityClassifier,
)


def test_error_summary_is_not_itself_a_hard_error() -> None:
    classifier = LatexDiagnosticSeverityClassifier()

    assert classifier.is_error_summary_line("(There was 1 error message)")
    assert not classifier.is_error_line("(There was 1 error message)")


def test_unknown_bibtex_error_before_summary_is_preserved() -> None:
    output = r"""
This is BibTeX, Version 0.99d
The top-level auxiliary file: preview.aux
A future BibTeX diagnostic that is not yet classified
(There was 1 error message)
Package natbib Warning: Citation `missing' undefined.
"""

    message = LatexCompilerDiagnosticExtractor().extract(output)

    assert "A future BibTeX diagnostic that is not yet classified" in message
    assert "(There was 1 error message)" in message
    assert "Citation `missing' undefined." in message


def test_missing_bibstyle_is_classified_as_hard_error() -> None:
    classifier = LatexDiagnosticSeverityClassifier()

    assert classifier.is_error_line(
        r"I found no \bibstyle command---while reading file preview.aux"
    )
