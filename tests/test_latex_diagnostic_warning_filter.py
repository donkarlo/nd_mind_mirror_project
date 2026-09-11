from nd_mind_mirror.core.render.latex.diagnostic.latex_compiler_diagnostic_extractor import (
    LatexCompilerDiagnosticExtractor,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_severity_classifier import (
    LatexDiagnosticSeverityClassifier,
)


def test_package_loading_line_is_not_promoted_to_warning():
    output = r"""
(/usr/local/texlive/2025/texmf-dist/tex/latex/l3packages/xparse/xparse.sty
Package hyperref Warning: Option `colorlinks' has already been used.
Package natbib Warning: Citation `missing' undefined.
Package natbib Warning: There were undefined citations.
"""

    message = LatexCompilerDiagnosticExtractor().extract(output)

    assert "xparse.sty" not in message
    assert message.splitlines()[0].startswith("Package hyperref Warning:")
    assert "Citation `missing' undefined." in message


def test_bibtex_repeated_entry_is_a_hard_error_and_precedes_warnings():
    output = r"""
Package natbib Warning: Citation `missing' undefined.
Repeated entry---line 42 of file bibliography.bib
I'm skipping whatever remains of this entry
(There was 1 error message)
"""

    message = LatexCompilerDiagnosticExtractor().extract(output)
    lines = message.splitlines()

    assert lines[0].startswith("Repeated entry---line 42")
    assert "I'm skipping whatever remains of this entry" in message
    assert "Citation `missing' undefined." in message


def test_package_loading_line_is_informational():
    classifier = LatexDiagnosticSeverityClassifier()
    line = "(/usr/local/texlive/2025/texmf-dist/tex/latex/l3packages/xparse/xparse.sty"

    assert classifier.kind_for_line(line) == "info"
