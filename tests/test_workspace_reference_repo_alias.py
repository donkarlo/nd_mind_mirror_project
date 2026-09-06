"""Regression tests for /repo reference resolution used by Ctrl+B navigation."""

from pathlib import Path

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


def test_resolves_repo_alias_from_configured_repo_root(tmp_path: Path) -> None:
    """Resolve /repo paths through the configured workspace instead of Linux root."""
    repository_root = tmp_path / "repo"
    project = repository_root / "project"
    project.mkdir(parents=True)
    target = project / "settings.yaml"
    target.write_text("value: true\n", encoding="utf-8")
    referring_file = project / "main.tex"
    referring_file.write_text("", encoding="utf-8")

    resolver = WorkspaceReferenceResolver(repository_root)

    assert resolver.resolve(
        "/repo/project/settings.yaml",
        referring_file,
    ) == target.resolve()


def test_repo_alias_keeps_command_suffix_resolution(tmp_path: Path) -> None:
    """Preserve command-specific extension lookup after mapping the /repo alias."""
    repository_root = tmp_path / "repo"
    assets = repository_root / "project" / "assets"
    assets.mkdir(parents=True)
    image = assets / "figure.png"
    image.write_bytes(b"png")
    referring_file = repository_root / "project" / "main.tex"
    referring_file.write_text("", encoding="utf-8")

    resolver = WorkspaceReferenceResolver(repository_root)

    assert resolver.resolve(
        "/repo/project/assets/figure",
        referring_file,
        command="includegraphics",
    ) == image.resolve()


def test_href_occurrence_targets_repo_alias_file(tmp_path: Path) -> None:
    """Expose a /repo href target to the Ctrl+B reference-opening controller."""
    repository_root = tmp_path / "repo"
    project = repository_root / "project"
    project.mkdir(parents=True)
    target = project / "notes.tex"
    target.write_text("notes", encoding="utf-8")
    referring_file = project / "main.tex"
    source = r"\href{/repo/project/notes.tex}{notes}"

    resolver = WorkspaceReferenceResolver(repository_root)
    occurrence = resolver.occurrence_at(
        source,
        referring_file,
        source.rindex("notes"),
    )

    assert occurrence is not None
    assert occurrence.target_path == target.resolve()
