from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)
from nd_mind_mirror.core.latex.input.latex_input_reference_validator import (
    LatexInputReferenceValidator,
)


def test_workspace_rooted_input_is_not_reported_missing(tmp_path: Path) -> None:
    target = (
        tmp_path
        / "nd_language_ai_project"
        / "src"
        / "nd_language_ai"
        / "formal"
        / "computer"
        / "programming"
        / "tex"
        / "latex"
        / "code_clips"
        / "external_graphviz.tex"
    )
    target.parent.mkdir(parents=True)
    target.write_text("% graphviz helper\n", encoding="utf-8")

    containing = (
        tmp_path
        / "nd_research_publication"
        / "src"
        / "kind"
        / "presentation"
        / "presentation.tex"
    )
    containing.parent.mkdir(parents=True)
    containing.write_text("% presentation\n", encoding="utf-8")

    source = (
        r"\input{/nd_language_ai_project/src/nd_language_ai/formal/"
        r"computer/programming/tex/latex/code_clips/external_graphviz.tex}"
    )

    resolver = WorkspaceRecursiveInputResolver(default_path=tmp_path)
    validator = LatexInputReferenceValidator(resolver)

    assert validator.first_missing_absolute_input(source, containing) is None


def test_missing_workspace_rooted_input_is_reported(tmp_path: Path) -> None:
    containing = tmp_path / "project" / "document.tex"
    containing.parent.mkdir(parents=True)
    containing.write_text("% document\n", encoding="utf-8")

    source = r"\include{/missing_project/chapter}"
    resolver = WorkspaceRecursiveInputResolver(default_path=tmp_path)
    validator = LatexInputReferenceValidator(resolver)

    assert (
        validator.first_missing_absolute_input(source, containing)
        == "/missing_project/chapter"
    )
