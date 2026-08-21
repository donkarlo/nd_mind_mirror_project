"""Create the Qt application, refresh the iPad transfer package, and launch the enhanced Mind Mirror window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import signal
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.graphic.ipad.package_builder import IpadPackageBuilder
from nd_mind_mirror.ui.icon.mind_mirror_icon import build_mind_mirror_icon
from nd_mind_mirror.ui.window.main.enhanced_main_window import EnhancedMainWindow


_LOG_PATH = Path.home() / ".local" / "state" / "nd_mind_mirror_project" / "startup.log"


def _log(message: str) -> None:
    """Append one best-effort startup/lifetime diagnostic line to the application state log."""
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as stream:
            stamp = datetime.now().isoformat(timespec="seconds")
            stream.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _refresh_ipad_package() -> None:
    """Rebuild nd_graphic.zip from the hidden Swift source before Qt starts whenever source files changed."""
    project_root = Path(__file__).resolve().parents[3]
    try:
        package = IpadPackageBuilder(project_root).refresh()
        if package is not None:
            _log(f"iPad transfer package ready: {package}")
    except Exception:
        _log("Could not refresh iPad transfer package:\n" + traceback.format_exc())


class MindMirrorApplication(QApplication):
    """Own QApplication startup and the lifetime of the enhanced main editor window."""

    @classmethod
    def run(cls, argv: list[str]) -> int:
        """Refresh the iPad package, create Qt, show EnhancedMainWindow, and return the event-loop exit code."""
        _refresh_ipad_package()
        _log("Creating QApplication")
        application = cls(argv)
        application.setApplicationName("nd_mind_mirror_project")
        application.setApplicationDisplayName("Mind Mirror")
        application.setOrganizationName("nd_mind_mirror")

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
            _log("Constructing EnhancedMainWindow")
            window = EnhancedMainWindow()
            if not icon.isNull():
                window.setWindowIcon(icon)
            window.destroyed.connect(lambda: _log("EnhancedMainWindow QObject destroyed"))
            window.show()
            _log("EnhancedMainWindow shown; entering Qt event loop")
        except BaseException:
            _log("Exception during EnhancedMainWindow startup:\n" + traceback.format_exc())
            raise

        previous_sigint = signal.getsignal(signal.SIGINT)

        def _handle_sigint(_signum, _frame) -> None:
            """Close the main window cleanly when Ctrl+C sends SIGINT from the launching terminal."""
            _log("SIGINT received; requesting EnhancedMainWindow close")
            QTimer.singleShot(0, window.close)

        signal.signal(signal.SIGINT, _handle_sigint)

        sigint_heartbeat = QTimer(application)
        sigint_heartbeat.setInterval(100)
        sigint_heartbeat.timeout.connect(lambda: None)
        sigint_heartbeat.start()

        try:
            code = application.exec()
        finally:
            sigint_heartbeat.stop()
            signal.signal(signal.SIGINT, previous_sigint)

        _log(f"QApplication.exec returned {code}")
        return code
