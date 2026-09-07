"""Regression tests for strict recursive Preview path resolution."""

from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_recursive_preview_never_finds_unrelated_suffix_match(tmp_path: Path) -> None:
    """A missing thesis-relative input must not pull a similarly named presentation file."""
    default_root = tmp_path / "repo"
    thesis_dir = default_root / "nd_research_publication" / "src" / "kind" / "thesis"
    thesis_dir.mkdir(parents=True)

    master = thesis_dir / "thesis.tex"
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\input{chapter/body/neuron/neuron.tex}\n"
        "\\end{document}\n"
    )
    master.write_text(source, encoding="utf-8")

    unrelated = (
        default_root
        / "nd_research_publication"
        / "src"
        / "kind"
        / "presentation"
        / "anatomy"
        / "body"
        / "nervous_system"
        / "neuron"
        / "neuron.tex"
    )
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text(
        "PRESENTATION_SENTINEL\n"
        "\\includegraphics{anatomy/body/nervous_system/neuron/neuron.png}\n",
        encoding="utf-8",
    )

    resolver = WorkspaceRecursiveInputResolver(default_root)
    rendered = resolver.resolve(source, master)

    assert "PRESENTATION_SENTINEL" not in rendered
    assert unrelated.resolve() not in resolver.resolved_paths
    assert any(
        "could not resolve \\input{chapter/body/neuron/neuron.tex}" in item
        for item in resolver.unresolved
    )


def test_recursive_preview_resolves_default_rooted_input(tmp_path: Path) -> None:
    """A leading slash is rooted at search.default_path before OS absolute fallback."""
    default_root = tmp_path / "repo"
    thesis_dir = default_root / "nd_research_publication" / "src" / "kind" / "thesis"
    thesis_dir.mkdir(parents=True)

    target = (
        default_root
        / "nd_robotic_ai_learning_project"
        / "src"
        / "robot"
        / "anatomy"
        / "anatomy.tex"
    )
    target.parent.mkdir(parents=True)
    target.write_text("\\section{Robot anatomy}\n", encoding="utf-8")

    master = thesis_dir / "thesis.tex"
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\input{/nd_robotic_ai_learning_project/src/robot/anatomy/anatomy.tex}\n"
        "\\end{document}\n"
    )
    master.write_text(source, encoding="utf-8")

    resolver = WorkspaceRecursiveInputResolver(default_root)
    rendered = resolver.resolve(source, master)

    assert "Robot anatomy" in rendered
    assert target.resolve() in resolver.resolved_paths


def test_application_wires_workspace_recursive_resolver() -> None:
    """The launched window must replace the generic resolver with the workspace resolver."""
    application_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/app/mind_mirror_application.py"
    ).read_text(encoding="utf-8")
    enhanced_window_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
    ).read_text(encoding="utf-8")

    assert "window = EnhancedMainWindow()" in application_source
    assert "self._configure_workspace_input_resolver()" in enhanced_window_source
    assert "WorkspaceRecursiveInputResolver(" in enhanced_window_source
