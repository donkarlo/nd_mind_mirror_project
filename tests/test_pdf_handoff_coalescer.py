"""Regression checks for safe Qt Quick PDF handoff coalescing."""

from pathlib import Path
import ast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COALESCER = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "preview"
    / "pdf"
    / "pdf_handoff_coalescer.py"
)
LATEX_PREVIEW = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "preview"
    / "latex"
    / "latex_preview.py"
)


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return "\n".join(
                lines[node.lineno - 1:node.end_lineno]
            )

    raise AssertionError(
        f"Function {function_name} not found in {path}"
    )


def test_latex_preview_routes_pdf_through_coalescer() -> None:
    show_pdf = _function_source(
        LATEX_PREVIEW,
        "show_pdf",
    )
    assert "_pdf_handoff_coalescer.request" in show_pdf
    assert "_pdf_view.show_pdf" not in show_pdf


def test_actual_qt_handoff_is_isolated() -> None:
    present = _function_source(
        LATEX_PREVIEW,
        "_present_pdf_now",
    )
    assert "_pdf_view.show_pdf" in present


def test_compile_error_discards_stale_queued_pdf() -> None:
    show_error = _function_source(
        LATEX_PREVIEW,
        "show_error",
    )
    assert "_pdf_handoff_coalescer.cancel_pending()" in show_error


def test_coalescer_keeps_only_one_pending_path() -> None:
    source = COALESCER.read_text(
        encoding="utf-8"
    )
    assert "self._pending_path = pdf_path" in source
    assert "self._timer.setSingleShot(True)" in source
    assert "_minimum_interval_ms" in source
