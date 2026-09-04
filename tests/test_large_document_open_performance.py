from pathlib import Path

from nd_mind_mirror.core.latex.structure.latex_structure_parser import (
    LatexStructureParser,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_structure_parser_keeps_full_large_document_line_numbers():
    lines = []
    expected = []
    for index in range(1, 2501):
        lines.append(f"ordinary prose {index}\n")
        if index % 250 == 0:
            expected.append((len(lines) + 1, f"Section {index}"))
            lines.append(f"\\section{{Section {index}}}\n")
    source = "".join(lines)

    structure = LatexStructureParser().parse(source)
    sections = [item for item in structure if item.kind == "section"]

    assert [(item.line_number, item.title) for item in sections] == expected


def test_large_structure_parser_does_not_recount_from_source_start_per_item():
    parser_source = _text(
        "src/nd_mind_mirror/core/latex/structure/latex_structure_parser.py"
    )
    assert "bisect_right" in parser_source
    assert "_line_starts" in parser_source
    assert 'structural.count("\\n", 0' not in parser_source


def test_large_structure_is_parsed_off_gui_thread_but_from_complete_source():
    panel_source = _text(
        "src/nd_mind_mirror/ui/panel/structure/latex_structure_panel.py"
    )
    worker_source = _text(
        "src/nd_mind_mirror/ui/panel/structure/latex_structure_parse_worker.py"
    )

    assert "LatexStructureParseWorker" in panel_source
    assert "self._source = str(source)" in panel_source
    assert "self._source," in panel_source
    assert "class LatexStructureParseWorker(QThread)" in worker_source
    assert "LatexStructureParser().parse(self._source)" in worker_source


def test_large_latex_highlighter_has_plain_prose_fast_path():
    highlighter_source = _text(
        "src/nd_mind_mirror/ui/highlighter/latex/latex_syntax_highlighter.py"
    )
    assert "_LARGE_DOCUMENT_THRESHOLD_CHARS" in highlighter_source
    assert "_may_contain_latex_token" in highlighter_source
    assert "if large_document and not self._may_contain_latex_token(value)" in highlighter_source
