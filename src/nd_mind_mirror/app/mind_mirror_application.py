from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import traceback

from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.icon.mind_mirror_icon import build_mind_mirror_icon
from nd_mind_mirror.ui.window.main.main_window import MainWindow


_LOG_PATH = Path.home() / ".local" / "state" / "nd_mind_mirror_project" / "startup.log"


def _log(message: str) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as stream:
            stamp = datetime.now().isoformat(timespec="seconds")
            stream.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


class MindMirrorApplication(QApplication):
    @classmethod
    def run(cls, argv: list[str]) -> int:
        _log("Creating QApplication")
        application = cls(argv)
        application.setApplicationName("nd_mind_mirror_project")
        application.setApplicationDisplayName("Mind Mirror")
        application.setOrganizationName("nd_mind_mirror")

        # Do not install/update .desktop files during application startup.
        # On older Ubuntu/GNOME/Qt combinations desktop integration is cosmetic
        # and must never be allowed to interfere with editor lifetime.
        try:
            application.setDesktopFileName("nd-mind-mirror")
        except (AttributeError, TypeError):
            pass

        application.aboutToQuit.connect(lambda: _log("QApplication aboutToQuit"))
        application.lastWindowClosed.connect(lambda: _log("QApplication lastWindowClosed"))

        try:
            icon = build_mind_mirror_icon()
            if not icon.isNull():
                application.setWindowIcon(icon)
            _log("Constructing MainWindow")
            window = MainWindow()
            if not icon.isNull():
                window.setWindowIcon(icon)
            window.destroyed.connect(lambda: _log("MainWindow QObject destroyed"))
            window.show()
            _log("MainWindow shown; entering Qt event loop")
        except BaseException:
            _log("Exception during MainWindow startup:\n" + traceback.format_exc())
            raise

        code = application.exec()
        _log(f"QApplication.exec returned {code}")
        return code
