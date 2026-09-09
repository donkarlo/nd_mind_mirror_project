from nd_mind_mirror.core.render.latex.diagnostic.latex_compiler_diagnostic_extractor import (
    LatexCompilerDiagnosticExtractor,
)


def test_undefined_control_sequence_keeps_latex_context_and_precedes_warnings():
    output = r"""
Package natbib Warning: Citation `missing-citation' on page 1 undefined.
/tmp/nd_mind_mirror_test/preview.tex:254: Undefined control sequence.
l.254 \brokencommand
                    {argument}
/tmp/nd_mind_mirror_test/preview.tex:254:  ==> Fatal error occurred, no output PDF file produced!
"""

    message = LatexCompilerDiagnosticExtractor().extract(output)
    lines = message.splitlines()

    assert "Undefined control sequence" in lines[0]
    assert r"l.254 \brokencommand" in message
    assert "{argument}" in message
    assert "Citation `missing-citation'" in message


def test_warning_only_output_is_still_reported():
    output = "Package natbib Warning: Citation `missing' undefined."

    message = LatexCompilerDiagnosticExtractor().extract(output)

    assert message == output


def test_empty_output_has_clear_fallback():
    message = LatexCompilerDiagnosticExtractor().extract("")

    assert message == "LaTeX compilation failed without diagnostic output."
