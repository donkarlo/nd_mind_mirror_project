"""Run one fresh project graphic bridge for each Mind Mirror application session."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QIODevice, QObject, QProcess, QProcessEnvironment
from PySide6.QtWidgets import QApplication


class GraphicBridgeSessionProcessController(QObject):
    """Start current bridge code even when a stale process still occupies the default port."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        project_root: str | Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._project_root = Path(project_root).expanduser().resolve()
        self._process: QProcess | None = None
        self._log_path = (
            Path.home()
            / "Desktop"
            / "repo"
            / "data"
            / "nd_mind_mirror_project"
            / "logs"
            / "graphic_bridge_process.log"
        )
        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.stop)

    def start(self) -> bool:
        """Start the canonical bridge; its launcher selects free ports on collisions."""
        if (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        ):
            return True

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        src_root = str(self._project_root / "src")
        existing_pythonpath = environment.value("PYTHONPATH", "")
        environment.insert(
            "PYTHONPATH",
            src_root if not existing_pythonpath else f"{src_root}:{existing_pythonpath}",
        )
        environment.insert("LANG", "C.UTF-8")
        environment.insert("LC_ALL", "C.UTF-8")
        process.setProcessEnvironment(environment)
        process.setWorkingDirectory(str(self._project_root))
        process.setProgram(sys.executable)
        process.setArguments(
            [
                "-m",
                "nd_mind_mirror.graphic.bridge",
                "--workspace",
                str(self._workspace_root),
            ]
        )
        process.setStandardOutputFile(
            str(self._log_path),
            QIODevice.OpenModeFlag.Append,
        )
        process.setStandardErrorFile(
            str(self._log_path),
            QIODevice.OpenModeFlag.Append,
        )
        process.start()
        self._process = process
        return bool(process.waitForStarted(1800))

    def stop(self) -> None:
        """Stop only the bridge process owned by this application session."""
        process = self._process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        process.terminate()
        if not process.waitForFinished(1200):
            process.kill()
            process.waitForFinished(700)
