"""Launch Mind Mirror with source-integrity and input/navigation safety controllers."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from nd_mind_mirror.app.mind_mirror_application import MindMirrorApplication
from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.window.main.latex_underscore_input_controller import (
    LatexUnderscoreInputController,
)
from nd_mind_mirror.ui.window.main.navigator_horizontal_scroll_controller import (
    NavigatorHorizontalScrollController,
)


class SafeMindMirrorApplication(MindMirrorApplication):
    """Install non-destructive editor behavior before the main window restores its session."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)

        self._latex_underscore_input_controller = LatexUnderscoreInputController(self)
        self.installEventFilter(self._latex_underscore_input_controller)

        self._navigator_horizontal_scroll_controller = NavigatorHorizontalScrollController(self)
        self.installEventFilter(self._navigator_horizontal_scroll_controller)

        self._recover_evil_document()

    @staticmethod
    def _repository_root(app_settings: YamlSettings) -> Path:
        return Path(app_settings.search_default_path).expanduser().resolve()

    @classmethod
    def _evil_paths(cls, app_settings: YamlSettings) -> tuple[Path, Path, Path]:
        directory = (
            cls._repository_root(app_settings)
            / "writing"
            / "litrature"
            / "story"
            / "evil"
        )
        return (
            directory / "evil_farsi.tex",
            directory / "evil_farsi_recovered_before_truncation.tex",
            directory / "evil_farsi_merged_recovered.tex",
        )

    @classmethod
    def _recover_evil_document(cls) -> None:
        """Create one conservative recovery file containing current edits plus lost old lines."""
        app_settings = YamlSettings()
        current_path, recovered_path, merged_path = cls._evil_paths(app_settings)
        if merged_path.is_file() or not current_path.is_file() or not recovered_path.is_file():
            return

        try:
            current_lines = current_path.read_text(encoding="utf-8").splitlines(keepends=True)
            recovered_lines = recovered_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            return

        matcher = SequenceMatcher(
            None,
            recovered_lines,
            current_lines,
            autojunk=False,
        )
        merged_lines: list[str] = []
        for tag, recovered_start, recovered_end, current_start, current_end in matcher.get_opcodes():
            if tag == "equal":
                merged_lines.extend(current_lines[current_start:current_end])
            elif tag == "insert":
                merged_lines.extend(current_lines[current_start:current_end])
            elif tag == "delete":
                merged_lines.extend(recovered_lines[recovered_start:recovered_end])
            else:
                # Treat a replacement as a deliberate newer edit. Large blocks that vanished
                # without replacement arrive as ``delete`` and are restored above.
                merged_lines.extend(current_lines[current_start:current_end])

        try:
            merged_path.write_text("".join(merged_lines), encoding="utf-8")
        except OSError:
            return
