from pathlib import Path

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_builder import (
    LatexDiagnosticBuilder,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_preview_source_map_builder import (
    LatexPreviewSourceMapBuilder,
)


def _all_nodes(node):
    yield node
    for child in node.children:
        yield from _all_nodes(child)


def test_diagnostic_tree_tracks_nested_input_and_missing_reference(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    master = workspace / "publication" / "human_mind_and_body.tex"
    body = workspace / "publication" / "part" / "body" / "body.tex"
    mind = workspace / "publication" / "part" / "mind" / "mind.tex"

    mind.parent.mkdir(parents=True)
    body.parent.mkdir(parents=True)
    master.parent.mkdir(parents=True, exist_ok=True)

    mind.write_text("Mind text.\n", encoding="utf-8")
    body.write_text(
        "\\include{../mind/mind.tex}\n"
        "\\input{missing/leaf.tex}\n",
        encoding="utf-8",
    )
    master_source = "\\input{part/body/body.tex}\n"
    master.write_text(master_source, encoding="utf-8")

    message = (
        "! LaTeX Error: File `missing/leaf.tex' not found.\n\n"
        f"{body}: could not resolve \\input{{missing/leaf.tex}}"
    )
    diagnostic = LatexDiagnosticBuilder(workspace).build(
        message=message,
        source_path=master,
        source=master_source,
    )

    nodes = list(_all_nodes(diagnostic.root))
    titles = [node.title for node in nodes]

    assert diagnostic.root.detail == str(workspace.resolve())
    assert "\\input{part/body/body.tex}" in titles
    assert "\\include{../mind/mind.tex}" in titles
    assert "\\input{missing/leaf.tex}" in titles

    missing = next(
        node
        for node in nodes
        if node.title == "\\input{missing/leaf.tex}"
    )
    assert missing.kind == "error"
    assert missing.source_path == body.resolve()
    assert missing.line == 2
    assert missing.column == 1


def test_default_rooted_input_is_displayed_below_search_default_path(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    master = workspace / "project" / "master.tex"
    shared = workspace / "shared" / "part.tex"
    master.parent.mkdir(parents=True)
    shared.parent.mkdir(parents=True)
    shared.write_text("Shared.\n", encoding="utf-8")
    source = "\\input{/shared/part.tex}\n"
    master.write_text(source, encoding="utf-8")

    diagnostic = LatexDiagnosticBuilder(workspace).build(
        message="! Undefined control sequence.",
        source_path=master,
        source=source,
    )
    nodes = list(_all_nodes(diagnostic.root))
    reference = next(
        node for node in nodes if node.title == "\\input{/shared/part.tex}"
    )

    assert reference.kind == "reference"
    assert reference.target_path == shared.resolve()
    assert "/shared/part.tex" in reference.detail


def test_preview_temp_line_maps_to_nested_source_file_and_line(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    template = tmp_path / "preview_template.tex"
    master = workspace / "project" / "master.tex"
    child = workspace / "project" / "part" / "child.tex"
    nested = workspace / "project" / "part" / "nested.tex"

    child.parent.mkdir(parents=True)
    template.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "{{ND_MIND_MIRROR_CONTENT}}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    nested.write_text("Nested one.\nNested two.\n", encoding="utf-8")
    child.write_text(
        "Child first.\n"
        "\\input{nested.tex}\n"
        "BROKEN $\n",
        encoding="utf-8",
    )
    source = "\\input{part/child.tex}\n"
    master.write_text(source, encoding="utf-8")

    source_map = LatexPreviewSourceMapBuilder(
        default_path=workspace,
        template_path=template,
    ).build(master, source)
    preview_line = next(
        index
        for index, line in enumerate(source_map.prepared_source.splitlines(), start=1)
        if "BROKEN $" in line
    )
    location = source_map.location_for_preview_line(preview_line)

    assert location.source_path == child.resolve()
    assert location.line == 3

    diagnostic = LatexDiagnosticBuilder(
        default_path=workspace,
        template_path=template,
    ).build(
        message=(
            f"/tmp/nd_mind_mirror_test/preview.tex:{preview_line}: "
            "Missing $ inserted."
        ),
        source_path=master,
        source=source,
    )
    nodes = list(_all_nodes(diagnostic.root))
    compiler_location = next(
        node
        for node in nodes
        if node.title == "Compiler location" and node.source_path == child.resolve()
    )

    assert compiler_location.line == 3
    assert f"generated preview line {preview_line}" in compiler_location.detail
