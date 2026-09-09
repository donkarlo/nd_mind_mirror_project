from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_node import (
    LatexDiagnosticNode,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_severity_classifier import (
    LatexDiagnosticSeverityClassifier,
)


WARNING_ONLY_OUTPUT = """
Package natbib Warning: Citation `vaswani-2017-attention-is-all-you-need' undefined.
Package natbib Warning: There were undefined citations.
Package rerunfilecheck Warning: File `preview.out' has changed.
Warning--I didn't find a database entry for "mickus-2024-language-models-and-the-paradigmatic-axisself"
Warning--can't use both author and editor fields in saussure-1916-course-in-general-linguistics
Warning--empty publisher in saussure-1916-course-in-general-linguistics
"""


def test_warning_only_compiler_message_is_not_an_error() -> None:
    classifier = LatexDiagnosticSeverityClassifier()

    assert classifier.is_warning_only(WARNING_ONLY_OUTPUT)
    assert not classifier.is_warning_only("! Undefined control sequence.")


def test_compilation_error_fallback_becomes_warning_for_natbib_warning() -> None:
    node = LatexDiagnosticNode(
        "Compilation error",
        "Package natbib Warning: Citation `missing-key' undefined.",
        "error",
    )

    assert node.title == "Compilation warnings"
    assert node.kind == "warning"


def test_compiler_output_warning_line_is_exposed_as_warning() -> None:
    node = LatexDiagnosticNode(
        "Warning--I didn't find a database entry for \"missing-key\"",
        "",
        "info",
    )

    assert node.kind == "warning"


def test_real_latex_error_remains_an_error() -> None:
    node = LatexDiagnosticNode(
        "Compilation error",
        "! Undefined control sequence.",
        "error",
    )

    assert node.title == "Compilation error"
    assert node.kind == "error"
