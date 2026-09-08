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


def test_recursive_preview_resolves_file_relative_input(tmp_path: Path) -> None:
    """A path without a leading slash resolves beside the referring file."""
    default_root = tmp_path / "repo"
    master_dir = default_root / "project" / "chapter"
    master_dir.mkdir(parents=True)

    target = master_dir / "part" / "body.tex"
    target.parent.mkdir(parents=True)
    target.write_text("\\section{Relative body}\n", encoding="utf-8")

    master = master_dir / "chapter.tex"
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\input{part/body.tex}\n"
        "\\end{document}\n"
    )

    resolver = WorkspaceRecursiveInputResolver(default_root)
    rendered = resolver.resolve(source, master)

    assert "Relative body" in rendered
    assert target.resolve() in resolver.resolved_paths


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


def test_recursive_preview_resolves_true_system_absolute_input(tmp_path: Path) -> None:
    """A true OS absolute path remains the fallback after default-rooted lookup."""
    default_root = tmp_path / "repo"
    default_root.mkdir(parents=True)
    master = default_root / "master.tex"

    target = tmp_path / "external" / "absolute.tex"
    target.parent.mkdir(parents=True)
    target.write_text("\\section{Absolute body}\n", encoding="utf-8")

    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        f"\\input{{{target.as_posix()}}}\n"
        "\\end{document}\n"
    )

    resolver = WorkspaceRecursiveInputResolver(default_root)
    rendered = resolver.resolve(source, master)

    assert "Absolute body" in rendered
    assert target.resolve() in resolver.resolved_paths


def test_renderer_owns_workspace_resolvers_from_construction() -> None:
    """Preview renderer must never begin life with the generic path resolver."""
    renderer_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/core/render/latex/latex_renderer.py"
    ).read_text(encoding="utf-8")

    assert "WorkspaceRecursiveInputResolver()" in renderer_source
    assert "WorkspaceGraphicDependencyResolver()" in renderer_source
    assert "def set_workspace_default_path(" in renderer_source


def test_session_restore_configures_workspace_root_before_restored_preview() -> None:
    """Restored tabs must receive search.default_path before they can request Preview."""
    enhanced_source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/enhanced_main_window_base.py"
    ).read_text(encoding="utf-8")

    restore_method = enhanced_source.split(
        "    def _restore_session(self) -> None:", 1
    )[1].split(
        "    def _save_session(self) -> None:", 1
    )[0]

    assert (
        restore_method.index("self._configure_workspace_input_resolver()")
        < restore_method.index("super()._restore_session()")
    )
    assert "renderer.set_workspace_default_path(" in enhanced_source
    assert "renderer._input_resolver =" not in enhanced_source
    assert "renderer._graphic_dependency_resolver =" not in enhanced_source
