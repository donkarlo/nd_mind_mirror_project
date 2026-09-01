"""Launch Mind Mirror with source-integrity and input/navigation safety controllers."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path

from PySide6.QtCore import QSettings

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

    _RECOVERED_EVIL_BOOKMARK_ANCHOR = (
        "در کودکی عاشق دختری شدم. نه صبر کن. از واژه ها دم دستی استفاده می کنم. "
        "همینطوری می گویم عشق. انگار کلمات نقل و نبات هستند که هر طور بخواهم آن ها را "
        "پخش کنم. بگذار حالا بنویسم توجهم را جلب کرد. نمی دانم، اما فکر می کنم این اولین "
        "بار بود که م"
    )

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)

        self._latex_underscore_input_controller = LatexUnderscoreInputController(self)
        self.installEventFilter(self._latex_underscore_input_controller)

        self._navigator_horizontal_scroll_controller = NavigatorHorizontalScrollController(self)
        self.installEventFilter(self._navigator_horizontal_scroll_controller)

        self._recover_evil_document()
        self._recover_lost_evil_bookmark()

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

    @classmethod
    def _recover_lost_evil_bookmark(cls) -> None:
        """Restore the bookmark that disappeared when the large Source window was truncated."""
        app_settings = YamlSettings()
        session = QSettings(
            str(app_settings.session_settings_path),
            QSettings.Format.IniFormat,
        )
        raw = session.value("editor/bookmarks_json", "{}")
        try:
            bookmarks = json.loads(str(raw or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            bookmarks = {}
        if not isinstance(bookmarks, dict):
            bookmarks = {}

        current_path, _recovered_path, _merged_path = cls._evil_paths(app_settings)
        source_path = str(current_path.resolve())
        items = bookmarks.get(source_path, [])
        if not isinstance(items, list):
            items = []

        anchor = cls._RECOVERED_EVIL_BOOKMARK_ANCHOR
        if any(
            str(item.get("anchor", "")) == anchor
            for item in items
            if isinstance(item, dict)
        ):
            return

        items.append(
            {
                "line": 417,
                "column": 1,
                "name": "",
                "anchor": anchor,
            }
        )
        bookmarks[source_path] = items
        session.setValue(
            "editor/bookmarks_json",
            json.dumps(bookmarks, ensure_ascii=False, separators=(",", ":")),
        )
        session.sync()
