from pathlib import Path

from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import (
    LatexShortcutProvider,
)


def test_loads_yaml_shortcuts(tmp_path: Path) -> None:
    path = tmp_path / "latex_shortcuts.yaml"
    path.write_text(
        """shortcuts:
  list:
    description: itemize list
    replacement: |-
      \\begin{itemize}
          \\item {{cursor}}
      \\end{itemize}
""",
        encoding="utf-8",
    )

    shortcuts = LatexShortcutProvider(path).load()

    assert len(shortcuts) == 1
    assert shortcuts[0].trigger == "list"
    assert shortcuts[0].description == "itemize list"
    assert "\\begin{itemize}" in shortcuts[0].replacement
    assert "{{cursor}}" in shortcuts[0].replacement
