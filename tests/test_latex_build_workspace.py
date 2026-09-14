from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_build_workspace import LatexBuildWorkspace


def test_successful_checkpoint_is_reused(tmp_path: Path) -> None:
    source = tmp_path / "story.tex"
    source.write_text("x", encoding="utf-8")
    workspace = LatexBuildWorkspace(tmp_path / "workspace")

    first = workspace.start_generation(1, source)
    first.tex_path.write_text("source", encoding="utf-8")
    (first.directory / "preview.aux").write_text("VALID AUX", encoding="utf-8")
    workspace.checkpoint_auxiliary()

    second = workspace.start_generation(2, source)
    assert (second.directory / "preview.aux").read_text(encoding="utf-8") == "VALID AUX"


def test_canceled_generation_cannot_poison_next_generation(tmp_path: Path) -> None:
    source = tmp_path / "story.tex"
    source.write_text("x", encoding="utf-8")
    workspace = LatexBuildWorkspace(tmp_path / "workspace")

    first = workspace.start_generation(1, source)
    (first.directory / "preview.aux").write_text("VALID AUX", encoding="utf-8")
    workspace.checkpoint_auxiliary()

    canceled = workspace.start_generation(2, source)
    (canceled.directory / "preview.aux").write_text(
        r"\@writefile{toc}{\contentsline {subsection}{\numberline {\LRE {",
        encoding="utf-8",
    )
    # No checkpoint: this generation models a killed compiler.

    third = workspace.start_generation(3, source)
    assert (third.directory / "preview.aux").read_text(encoding="utf-8") == "VALID AUX"


def test_auxiliary_cache_is_scoped_per_source(tmp_path: Path) -> None:
    source_a = tmp_path / "a.tex"
    source_b = tmp_path / "b.tex"
    source_a.write_text("a", encoding="utf-8")
    source_b.write_text("b", encoding="utf-8")
    workspace = LatexBuildWorkspace(tmp_path / "workspace")

    first = workspace.start_generation(1, source_a)
    (first.directory / "preview.aux").write_text("A AUX", encoding="utf-8")
    workspace.checkpoint_auxiliary()

    second = workspace.start_generation(2, source_b)
    assert not (second.directory / "preview.aux").exists()


def test_reset_active_outputs_keeps_source_only(tmp_path: Path) -> None:
    workspace = LatexBuildWorkspace(tmp_path / "workspace")
    build = workspace.start_generation(1, tmp_path / "story.tex")
    build.tex_path.write_text("source", encoding="utf-8")
    build.pdf_path.write_bytes(b"pdf")
    (build.directory / "preview.aux").write_text("aux", encoding="utf-8")

    workspace.reset_active_outputs(keep_tex=True)

    assert build.tex_path.read_text(encoding="utf-8") == "source"
    assert not build.pdf_path.exists()
    assert not (build.directory / "preview.aux").exists()
