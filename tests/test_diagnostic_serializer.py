from pathlib import Path

import yaml

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import LatexDiagnostic
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_node import (
    LatexDiagnosticNode,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_serializer import (
    LatexDiagnosticSerializer,
)


def _diagnostic() -> LatexDiagnostic:
    root = LatexDiagnosticNode("repo", kind="workspace")
    file_node = root.add_child(
        LatexDiagnosticNode(
            "chapter.tex",
            kind="file",
            source_path=Path("/tmp/chapter.tex"),
            line=12,
            column=3,
        )
    )
    file_node.add_child(
        LatexDiagnosticNode(
            "Missing $ inserted",
            detail="compiler location",
            kind="error",
            source_path=Path("/tmp/chapter.tex"),
            line=12,
            column=3,
        )
    )
    return LatexDiagnostic(
        summary="Missing $ inserted",
        raw_message="preview.tex:44: Missing $ inserted.",
        root=root,
    )


def test_text_contains_raw_output_and_tree() -> None:
    text = LatexDiagnosticSerializer().to_text(_diagnostic())
    assert "Raw compiler output:" in text
    assert "preview.tex:44: Missing $ inserted." in text
    assert "[error] Missing $ inserted" in text
    assert "/tmp/chapter.tex:12:3" in text


def test_yaml_round_trips_complete_diagnostic() -> None:
    data = yaml.safe_load(LatexDiagnosticSerializer().to_yaml(_diagnostic()))
    assert data["summary"] == "Missing $ inserted"
    assert data["raw_message"] == "preview.tex:44: Missing $ inserted."
    assert data["tree"]["children"][0]["children"][0]["kind"] == "error"
